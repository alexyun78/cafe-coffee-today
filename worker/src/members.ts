// 92도씨 회원 — 시크릿 QR 카드로 가입하고 원두를 하나씩 여는 수집 게임 (docs/MEMBERS.md)
//
// QR 한 장 = 초대장이자 **그 원두의 열쇠**다. 매장에서 필터 커피를 내면서 원두 카드를
// 건네고, 손님이 그 카드의 QR 을 찍으면
//   - 처음이면 → 구글 계정으로 가입 + 그 원두가 열린다 (첫 번째 열쇠)
//   - 이미 회원이면 → 그 원두만 열린다
// 미션으로 지정한 원두(`bean_missions`)는 열기 전까지 /beans 목록에서 자물쇠로 가려진다.
//
// 세션은 관리자와 같은 HMAC 서명 쿠키(util.signToken)를 salt 만 바꿔 쓴다.
// 스키마: scripts/members_schema.sql + scripts/members_mission_migration.sql
import { Hono } from 'hono'
import { Env, Row, utcNowISO, signToken, verifyToken, getCookie, b64urlDecode, b64urlEncode } from './util'
import { requirePin } from './auth'
import { BEAN_CARDS, beanBrief, beanById, activeMissionIds, myBeanRecords } from './beancat'

export type MemberEnv = { Bindings: Env; Variables: { member: Row } }
export const memberRoutes = new Hono<MemberEnv>()

const MEMBER_COOKIE = 'mem'
const MEMBER_SALT = 'member-token-v1'
const MEMBER_TTL_SEC = 60 * 60 * 24 * 90 // 90일 — 손님이 매번 다시 로그인하지 않도록 길게

const STATE_COOKIE = 'oas'
const STATE_SALT = 'oauth-state-v1'
const STATE_TTL_SEC = 600 // OAuth 왕복은 10분이면 충분

const GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
const GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
const GOOGLE_ISS = new Set(['https://accounts.google.com', 'accounts.google.com'])

// ---------- 초대 코드 ----------

// 혼동되는 글자(I, O, 0, 1)를 뺀 32자 — 손님이 QR 대신 손으로 옮겨 적어도 헷갈리지 않는다.
const CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
const CODE_LEN = 10
const CODE_RE = /^[A-Z0-9]{6,24}$/

/** 입력받은 코드를 저장 형태로 정규화 (소문자, 하이픈, 공백 허용) */
export function normCode(v: any): string {
  return String(v ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '')
}

/** 32자 알파벳 = 5비트라 바이트를 32로 나눈 나머지가 그대로 균등하다 */
function newCode(): string {
  const bytes = new Uint8Array(CODE_LEN)
  crypto.getRandomValues(bytes)
  return [...bytes].map((b) => CODE_ALPHABET[b % CODE_ALPHABET.length]).join('')
}

/** 인쇄용 표기 — ABCDE-FGHJK */
export const prettyCode = (code: string) => `${code.slice(0, 5)}-${code.slice(5)}`

type InviteState = 'ok' | 'not_found' | 'used' | 'expired'

async function checkInvite(db: D1Database, code: string): Promise<{ state: InviteState; row: Row | null }> {
  if (!CODE_RE.test(code)) return { state: 'not_found', row: null }
  const row = await db.prepare('SELECT * FROM invite_codes WHERE code=?').bind(code).first<Row>()
  if (!row) return { state: 'not_found', row: null }
  if (row.redeemed_by) return { state: 'used', row }
  if (row.expires_at && row.expires_at < utcNowISO()) return { state: 'expired', row }
  return { state: 'ok', row }
}

// ---------- 세션 ----------

function cookieHeader(name: string, value: string, maxAge: number): string {
  return `${name}=${value}; Max-Age=${maxAge}; Path=/; HttpOnly; SameSite=Lax; Secure`
}

const PUBLIC_FIELDS =
  'id, google_sub, email, name, picture, nickname, invite_code, status, joined_at, last_login_at'

/** 로그인한 회원 행. 비로그인이거나 정지된 계정이면 null.
 *  라우터 종류를 가리지 않도록 env 와 Request 만 받는다 (beans.ts 에서도 쓴다). */
export async function currentMember(env: Env, req: Request): Promise<Row | null> {
  const tok = getCookie(req, MEMBER_COOKIE)
  if (!tok) return null
  const payload = await verifyToken(env.SESSION_SECRET, MEMBER_SALT, tok, MEMBER_TTL_SEC)
  const id = Number(payload?.mid)
  if (!id) return null
  const row = await env.DB.prepare(`SELECT ${PUBLIC_FIELDS} FROM members WHERE id=?`).bind(id).first<Row>()
  if (!row || row.status !== '활성') return null
  return row
}

/** 회원 전용 라우트 가드 */
export async function requireMember(c: any, next: () => Promise<void>) {
  const m = await currentMember(c.env, c.req.raw)
  if (!m) return c.json({ success: false, error: 'login required' }, 401)
  c.set('member', m)
  await next()
}

const memberPublic = (m: Row) => ({
  id: m.id,
  email: m.email,
  name: m.name,
  picture: m.picture,
  nickname: m.nickname,
  joined_at: m.joined_at,
})

// ---------- 해금 ----------

type UnlockResult =
  | { ok: true; already: boolean; bean_id: string }
  | { ok: false; reason: 'no_bean' | 'invite_used' | 'invite_expired' | 'invite_not_found' }

/** 코드 한 장으로 원두 하나를 연다.
 *  - 이미 연 원두면 **코드를 소진하지 않는다** — 손님이 그 카드를 다른 사람에게 넘길 수 있게.
 *  - 코드 소진은 조건부 UPDATE 라 같은 카드를 동시에 써도 한 명만 성공한다. */
async function redeemForBean(db: D1Database, memberId: number, code: string): Promise<UnlockResult> {
  const { state, row } = await checkInvite(db, code)
  if (state !== 'ok') return { ok: false, reason: `invite_${state}` as any }

  const beanId = row?.bean_id ? String(row.bean_id) : ''
  if (!beanId || !beanById(beanId)) return { ok: false, reason: 'no_bean' }

  const mine = await db
    .prepare('SELECT id FROM bean_unlocks WHERE member_id=? AND bean_id=?')
    .bind(memberId, beanId)
    .first<Row>()
  if (mine) return { ok: true, already: true, bean_id: beanId }

  const now = utcNowISO()
  const claim = await db
    .prepare('UPDATE invite_codes SET redeemed_by=?, redeemed_at=? WHERE code=? AND redeemed_by IS NULL')
    .bind(memberId, now, code)
    .run()
  if (!claim.meta.changes) return { ok: false, reason: 'invite_used' }

  await db
    .prepare(
      'INSERT INTO bean_unlocks (member_id, bean_id, invite_code, unlocked_at) VALUES (?,?,?,?) ' +
        'ON CONFLICT(member_id, bean_id) DO NOTHING',
    )
    .bind(memberId, beanId, code, now)
    .run()
  return { ok: true, already: false, bean_id: beanId }
}

/** 마이페이지가 쓰는 상태 — 미션 진행 + 내가 맛본 원두 전체 */
async function memberBeanState(db: D1Database, memberId: number | null) {
  const [missions, mine] = await Promise.all([activeMissionIds(db), myBeanRecords(db, memberId)])

  const slots = missions.map((id) => {
    const rec = mine.get(id)
    const card = beanById(id)
    return rec
      ? {
          locked: false,
          id,
          name_ko: card?.name_ko ?? '',
          tasted_at: rec.tasted_at,
          rating: rec.rating,
          has_note: Boolean(rec.body),
        }
      : { locked: true }
  })
  const opened = slots.filter((s) => !s.locked).length

  // 미션이 아닌 원두도 QR 을 찍었으면 기록에 남는다 — 최근 맛본 순
  const tasted = [...mine.entries()]
    .map(([id, rec]) => ({
      id,
      name_ko: beanById(id)?.name_ko ?? id,
      mission: missions.includes(id),
      tasted_at: rec.tasted_at,
      rating: rec.rating,
      has_note: Boolean(rec.body),
    }))
    .sort((a, b) => (a.tasted_at < b.tasted_at ? 1 : a.tasted_at > b.tasted_at ? -1 : 0))

  return {
    total: missions.length,
    unlocked: opened,
    complete: missions.length > 0 && opened === missions.length,
    slots,
    tasted,
    tasted_count: tasted.length,
  }
}

// ---------- 구글 OAuth ----------

/** 구글에 넘길 리디렉션 URI. **구글 콘솔에 등록한 값과 한 글자도 다르면 안 되므로**
 *  요청이 어떻게 들어왔든 정규 주소 하나로 고정한다.
 *   - www 는 떼고 (www 로 들어온 손님도 같은 URI 를 쓰게)
 *   - http 는 https 로 (구글은 localhost 말고는 http 리디렉션을 거부한다)
 *   - SITE_HOST 를 주면 그 호스트로 강제 (wrangler.jsonc 의 vars)
 *  로컬 개발(localhost)만 요청 주소 그대로 둔다. */
const redirectUri = (c: any) => {
  const u = new URL(c.req.url)
  if (u.hostname === 'localhost' || u.hostname === '127.0.0.1')
    return new URL('/auth/google/callback', c.req.url).toString()
  const host = (c.env.SITE_HOST || u.host).replace(/^www\./, '')
  return `https://${host}/auth/google/callback`
}

/** 로그인 후 돌아갈 경로. 외부 사이트로 튕기지 않도록 내부 절대경로만 허용한다 */
function safeNext(v: any): string {
  const s = String(v ?? '')
  if (!s.startsWith('/') || s.startsWith('//')) return ''
  return /^[A-Za-z0-9\-._~/?#\[\]@!$&()*+,;=:%]*$/.test(s) ? s : ''
}

function randNonce(): string {
  const b = new Uint8Array(16)
  crypto.getRandomValues(b)
  return b64urlEncode(b)
}

memberRoutes.get('/auth/google/start', async (c) => {
  if (!c.env.GOOGLE_CLIENT_ID) return c.redirect('/login?error=not_configured', 302)
  const invite = normCode(c.req.query('invite'))
  const next = safeNext(c.req.query('next'))
  const nonce = randNonce()
  const state = await signToken(c.env.SESSION_SECRET, STATE_SALT, { n: nonce, invite, next })
  c.header('Set-Cookie', cookieHeader(STATE_COOKIE, state, STATE_TTL_SEC))

  const url = new URL(GOOGLE_AUTH_URL)
  url.searchParams.set('client_id', c.env.GOOGLE_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri(c))
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid email profile')
  url.searchParams.set('state', nonce)
  url.searchParams.set('prompt', 'select_account')
  return c.redirect(url.toString(), 302)
})

/** id_token 은 구글 토큰 엔드포인트에서 TLS 로 직접 받은 것이라 서명 재검증 대신
 *  발급자와 대상(aud), 만료만 확인한다 (구글 문서가 허용하는 경로). */
function readIdToken(idToken: string, clientId: string): Row | null {
  const parts = (idToken || '').split('.')
  if (parts.length !== 3) return null
  let p: Row
  try {
    p = JSON.parse(new TextDecoder().decode(b64urlDecode(parts[1])))
  } catch {
    return null
  }
  if (!p.sub || !GOOGLE_ISS.has(String(p.iss))) return null
  if (p.aud !== clientId) return null
  if (typeof p.exp !== 'number' || p.exp < Math.floor(Date.now() / 1000)) return null
  return p
}

memberRoutes.get('/auth/google/callback', async (c) => {
  const db = c.env.DB
  const fail = (reason: string) => {
    c.header('Set-Cookie', cookieHeader(STATE_COOKIE, '', 0))
    return c.redirect(`/login?error=${reason}`, 302)
  }

  // 1) state 대조 (CSRF) — 쿠키에 서명해 둔 nonce 와 구글이 되돌려준 값이 같아야 한다
  const stateTok = getCookie(c.req.raw, STATE_COOKIE)
  const st = stateTok ? await verifyToken(c.env.SESSION_SECRET, STATE_SALT, stateTok, STATE_TTL_SEC) : null
  if (!st || !st.n || st.n !== c.req.query('state')) return fail('state')
  if (c.req.query('error')) return fail('cancelled')

  const code = c.req.query('code')
  if (!code) return fail('cancelled')

  // 2) 인가 코드를 토큰으로 교환
  let idPayload: Row | null = null
  try {
    const res = await fetch(GOOGLE_TOKEN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: c.env.GOOGLE_CLIENT_ID || '',
        client_secret: c.env.GOOGLE_CLIENT_SECRET || '',
        redirect_uri: redirectUri(c),
        grant_type: 'authorization_code',
      }),
      signal: AbortSignal.timeout(10000),
    })
    if (!res.ok) return fail('token')
    const tok = (await res.json()) as Row
    idPayload = readIdToken(String(tok.id_token || ''), c.env.GOOGLE_CLIENT_ID || '')
  } catch {
    return fail('token')
  }
  if (!idPayload) return fail('token')
  if (idPayload.email && idPayload.email_verified === false) return fail('email_unverified')

  const sub = String(idPayload.sub)
  const now = utcNowISO()
  const invite = normCode(st.invite)
  const next = safeNext(st.next)

  let member = await db.prepare('SELECT * FROM members WHERE google_sub=?').bind(sub).first<Row>()
  let created = false

  if (!member) {
    // 3) 신규는 카드(초대 코드)가 반드시 있어야 한다
    if (!invite) return fail('invite_required')
    const { state } = await checkInvite(db, invite)
    if (state !== 'ok') return fail(`invite_${state}`)

    await db
      .prepare(
        'INSERT INTO members (google_sub, email, name, picture, invite_code, status, joined_at, last_login_at) ' +
          "VALUES (?,?,?,?,?,'활성',?,?)",
      )
      .bind(sub, idPayload.email ?? null, idPayload.name ?? null, idPayload.picture ?? null, invite, now, now)
      .run()
    member = await db.prepare('SELECT * FROM members WHERE google_sub=?').bind(sub).first<Row>()
    if (!member) return fail('server')
    created = true
  } else {
    if (member.status !== '활성') return fail('suspended')
    // 구글 쪽 프로필이 바뀌었을 수 있으니 로그인할 때마다 갱신한다 (호칭은 건드리지 않는다)
    await db
      .prepare('UPDATE members SET email=?, name=?, picture=?, last_login_at=? WHERE id=?')
      .bind(idPayload.email ?? null, idPayload.name ?? null, idPayload.picture ?? null, now, member.id)
      .run()
  }

  // 4) 카드에 묶인 원두를 연다. 원두가 안 묶인 순수 초대장이면 코드만 소진한다.
  let unlockedBean = ''
  if (invite) {
    const r = await redeemForBean(db, Number(member.id), invite)
    if (r.ok) {
      unlockedBean = r.bean_id
    } else if (r.reason === 'no_bean') {
      await db
        .prepare('UPDATE invite_codes SET redeemed_by=?, redeemed_at=? WHERE code=? AND redeemed_by IS NULL')
        .bind(member.id, now, invite)
        .run()
    } else if (created) {
      // 가입 직전 확인까지 통과했는데 코드가 사라졌다 — 만든 계정을 되돌린다
      await db.prepare('DELETE FROM members WHERE id=?').bind(member.id).run()
      return fail(r.reason)
    }
  }

  const token = await signToken(c.env.SESSION_SECRET, MEMBER_SALT, { mid: member.id })
  c.header('Set-Cookie', cookieHeader(STATE_COOKIE, '', 0))
  c.header('Set-Cookie', cookieHeader(MEMBER_COOKIE, token, MEMBER_TTL_SEC), { append: true })

  if (created) return c.redirect(`/me?welcome=1${unlockedBean ? `&unlocked=${unlockedBean}` : ''}`, 302)
  if (unlockedBean) return c.redirect(`/beans/${unlockedBean}?unlocked=1`, 302)
  return c.redirect(next || '/me', 302)
})

// ---------- 공개 API ----------

memberRoutes.get('/api/member/me', async (c) => {
  const m = await currentMember(c.env, c.req.raw)
  return c.json({
    success: true,
    login_enabled: Boolean(c.env.GOOGLE_CLIENT_ID),
    member: m ? memberPublic(m) : null,
    progress: await memberBeanState(c.env.DB, m ? Number(m.id) : null),
  })
})

memberRoutes.post('/api/member/logout', (c) => {
  c.header('Set-Cookie', cookieHeader(MEMBER_COOKIE, '', 0))
  return c.json({ success: true })
})

/** 가입·해금 랜딩(/join/<code>)이 카드 상태를 확인한다.
 *  코드에 묶인 원두 이름은 알려준다 — 손님은 그 커피를 이미 마셨으니 비밀이 아니다. */
memberRoutes.get('/api/member/invite/:code', async (c) => {
  const code = normCode(c.req.param('code'))
  const { state, row } = await checkInvite(c.env.DB, code)
  const m = await currentMember(c.env, c.req.raw)
  const beanId = row?.bean_id ? String(row.bean_id) : ''
  const card = beanId ? beanById(beanId) : null

  let already = false
  if (m && beanId) {
    const hit = await c.env.DB
      .prepare('SELECT 1 AS x FROM bean_unlocks WHERE member_id=? AND bean_id=?')
      .bind(m.id, beanId)
      .first<Row>()
    already = Boolean(hit)
  }

  return c.json({
    success: true,
    valid: state === 'ok',
    state,
    code_pretty: CODE_RE.test(code) ? prettyCode(code) : '',
    login_enabled: Boolean(c.env.GOOGLE_CLIENT_ID),
    logged_in: Boolean(m),
    already_unlocked: already,
    bean: card ? { id: card.id, name_ko: card.name_ko ?? '', country: card.country ?? '' } : null,
  })
})

/** 이미 로그인한 회원이 새 카드를 찍었을 때 — 가입 없이 원두만 연다 */
memberRoutes.post('/api/member/unlock', requireMember, async (c) => {
  const m = c.get('member')
  const data = (await c.req.json().catch(() => ({}))) as Row
  const code = normCode(data.code)
  const r = await redeemForBean(c.env.DB, Number(m.id), code)
  if (!r.ok) return c.json({ success: false, error: r.reason }, 400)
  const card = beanById(r.bean_id)
  return c.json({
    success: true,
    already: r.already,
    bean: { id: r.bean_id, name_ko: card?.name_ko ?? '' },
    progress: await memberBeanState(c.env.DB, Number(m.id)),
  })
})

/** 본인이 정하는 매장 호칭 */
memberRoutes.put('/api/member/me', requireMember, async (c) => {
  const m = c.get('member')
  const data = (await c.req.json().catch(() => ({}))) as Row
  const nickname = String(data.nickname ?? '').trim().slice(0, 20) || null
  await c.env.DB.prepare('UPDATE members SET nickname=? WHERE id=?').bind(nickname, m.id).run()
  return c.json({ success: true, member: { ...memberPublic(m), nickname } })
})

// ---------- 원두 감상 (본인만 열람) ----------

const RATINGS = new Set(['좋아요', '중간', '싫어요'])
const NOTE_MAX = 2000

/** 내가 맛본 원두에만 감상을 남길 수 있다. 빈 값으로 보내면 지운다. */
memberRoutes.put('/api/member/notes/:beanId', requireMember, async (c) => {
  const m = c.get('member')
  const beanId = c.req.param('beanId')
  if (!beanById(beanId)) return c.json({ success: false, error: 'unknown bean' }, 404)

  // QR 을 찍어 실제로 맛본 원두여야 한다 (본인의 원두 카드에만 쓴다)
  const tasted = await c.env.DB
    .prepare('SELECT unlocked_at FROM bean_unlocks WHERE member_id=? AND bean_id=?')
    .bind(m.id, beanId)
    .first<Row>()
  if (!tasted) return c.json({ success: false, error: 'not tasted' }, 403)

  const data = (await c.req.json().catch(() => ({}))) as Row
  const rating = RATINGS.has(String(data.rating)) ? String(data.rating) : null
  const body = String(data.body ?? '').trim().slice(0, NOTE_MAX) || null
  const now = utcNowISO()

  if (!rating && !body) {
    await c.env.DB.prepare('DELETE FROM bean_notes WHERE member_id=? AND bean_id=?').bind(m.id, beanId).run()
    return c.json({ success: true, note: null })
  }

  await c.env.DB
    .prepare(
      'INSERT INTO bean_notes (member_id, bean_id, rating, body, created_at, updated_at) VALUES (?,?,?,?,?,?) ' +
        'ON CONFLICT(member_id, bean_id) DO UPDATE SET rating=excluded.rating, body=excluded.body, updated_at=excluded.updated_at',
    )
    .bind(m.id, beanId, rating, body, now, now)
    .run()
  return c.json({ success: true, note: { rating, body, updated_at: now, tasted_at: tasted.unlocked_at } })
})

// ---------- 관리자 API ----------

for (const p of ['/api/member/admin', '/api/member/admin/*']) memberRoutes.use(p, requirePin)

memberRoutes.get('/api/member/admin/overview', async (c) => {
  const db = c.env.DB
  const [members, invites, batches, unlocks] = await db.batch([
    db.prepare(`SELECT ${PUBLIC_FIELDS} FROM members ORDER BY joined_at DESC LIMIT 500`),
    db.prepare(
      'SELECT COUNT(*) AS total, SUM(CASE WHEN redeemed_by IS NULL THEN 1 ELSE 0 END) AS unused FROM invite_codes',
    ),
    db.prepare(
      "SELECT COALESCE(bean_id,'(원두 없음)') AS bean_id, COALESCE(batch,'(묶음 없음)') AS batch, COUNT(*) AS total, " +
        'SUM(CASE WHEN redeemed_by IS NULL THEN 1 ELSE 0 END) AS unused, MIN(created_at) AS created_at ' +
        'FROM invite_codes GROUP BY bean_id, batch ORDER BY created_at DESC',
    ),
    db.prepare('SELECT member_id, COUNT(*) AS c FROM bean_unlocks GROUP BY member_id'),
  ])
  const inv = (invites.results[0] as Row) || {}
  const unlockMap: Record<number, number> = {}
  for (const r of unlocks.results as Row[]) unlockMap[Number(r.member_id)] = Number(r.c)

  const missions = await activeMissionIds(db)
  return c.json({
    success: true,
    members: (members.results as Row[]).map((m) => ({ ...m, unlocked: unlockMap[Number(m.id)] ?? 0 })),
    invite_total: inv.total ?? 0,
    invite_unused: inv.unused ?? 0,
    batches: (batches.results as Row[]).map((b) => ({
      ...b,
      bean_name: beanById(String(b.bean_id))?.name_ko ?? String(b.bean_id),
    })),
    mission_total: missions.length,
  })
})

/** 원두 카드 전체 + 미션 지정 여부 (관리자 화면의 미션 고르기) */
memberRoutes.get('/api/member/admin/beans', async (c) => {
  const { results } = await c.env.DB
    .prepare('SELECT bean_id, sort_order, active FROM bean_missions')
    .all<Row>()
  const mission = new Map(results.map((r) => [String(r.bean_id), r]))
  const counts = await c.env.DB
    .prepare('SELECT bean_id, COUNT(*) AS c FROM bean_unlocks GROUP BY bean_id')
    .all<Row>()
  const openedBy: Record<string, number> = {}
  for (const r of counts.results as Row[]) openedBy[String(r.bean_id)] = Number(r.c)

  return c.json({
    success: true,
    items: BEAN_CARDS.map((b) => {
      const m = mission.get(String(b.id))
      return {
        ...beanBrief(b),
        mission: Boolean(m && m.active),
        sort_order: m ? Number(m.sort_order) : 0,
        opened_by: openedBy[String(b.id)] ?? 0,
      }
    }),
  })
})

/** 미션 원두 지정 — 보낸 목록이 곧 미션 세트가 된다 (순서 = 배열 순서) */
memberRoutes.put('/api/member/admin/missions', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  const ids: string[] = Array.isArray(data.bean_ids)
    ? data.bean_ids.map((x: any) => String(x)).filter((id: string) => Boolean(beanById(id)))
    : []
  const now = utcNowISO()
  const stmts = [c.env.DB.prepare('UPDATE bean_missions SET active=0')]
  ids.forEach((id, i) => {
    stmts.push(
      c.env.DB
        .prepare(
          'INSERT INTO bean_missions (bean_id, sort_order, active, created_at) VALUES (?,?,1,?) ' +
            'ON CONFLICT(bean_id) DO UPDATE SET sort_order=excluded.sort_order, active=1',
        )
        .bind(id, i, now),
    )
  })
  await c.env.DB.batch(stmts)
  return c.json({ success: true, bean_ids: ids })
})

/** 초대 코드 조회 — 인쇄 시트(/member-cards)가 읽는다 */
memberRoutes.get('/api/member/admin/invites', async (c) => {
  const batch = c.req.query('batch') || ''
  const beanId = c.req.query('bean') || ''
  const onlyUnused = c.req.query('unused') !== '0'
  const where: string[] = []
  const binds: any[] = []
  if (batch) {
    where.push('batch=?')
    binds.push(batch)
  }
  if (beanId === 'none') {
    where.push('bean_id IS NULL') // 원두 없이 가입만 시키는 초대 카드
  } else if (beanId) {
    where.push('bean_id=?')
    binds.push(beanId)
  }
  if (onlyUnused) where.push('redeemed_by IS NULL')
  const sql =
    'SELECT code, batch, bean_id, note, created_at, expires_at, redeemed_by, redeemed_at FROM invite_codes' +
    (where.length ? ` WHERE ${where.join(' AND ')}` : '') +
    ' ORDER BY created_at DESC, code LIMIT 500'
  const { results } = await c.env.DB.prepare(sql).bind(...binds).all<Row>()
  return c.json({
    success: true,
    items: results.map((r) => {
      const card = r.bean_id ? beanById(String(r.bean_id)) : null
      return {
        ...r,
        pretty: prettyCode(String(r.code)),
        bean_name: card?.name_ko ?? '',
        bean_name_en: card?.name_en ?? '',
        bean_country: card?.country ?? '',
        bean_process: card?.process ?? '',
        bean_one_liner: card?.one_liner ?? '',
        bean_cup_notes: card?.cup_notes ?? [],
      }
    }),
  })
})

/** 카드 발급 — 원두 하나에 대해 인쇄할 장수만큼 고유 코드를 찍는다 */
memberRoutes.post('/api/member/admin/invites', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  const count = Math.min(200, Math.max(1, Math.floor(Number(data.count) || 0)))
  const batch = String(data.batch ?? '').trim().slice(0, 40) || null
  const note = String(data.note ?? '').trim().slice(0, 200) || null
  const beanId = String(data.bean_id ?? '').trim()
  if (beanId && !beanById(beanId)) return c.json({ success: false, error: 'unknown bean' }, 400)
  const expires = /^\d{4}-\d{2}-\d{2}$/.test(String(data.expires_at ?? '')) ? `${data.expires_at}T23:59:59Z` : null
  const now = utcNowISO()

  const codes: string[] = []
  const seen = new Set<string>()
  while (codes.length < count) {
    const code = newCode()
    if (seen.has(code)) continue
    seen.add(code)
    codes.push(code)
  }
  await c.env.DB.batch(
    codes.map((code) =>
      c.env.DB
        .prepare(
          'INSERT INTO invite_codes (code, batch, bean_id, note, created_at, expires_at) VALUES (?,?,?,?,?,?) ' +
            'ON CONFLICT(code) DO NOTHING',
        )
        .bind(code, batch, beanId || null, note, now, expires),
    ),
  )
  return c.json({
    success: true,
    batch,
    bean_id: beanId || null,
    count: codes.length,
    codes: codes.map((code) => ({ code, pretty: prettyCode(code) })),
  })
})

/** 아직 안 쓴 코드만 폐기할 수 있다 (이미 가입·해금에 쓰인 코드는 기록으로 남긴다) */
memberRoutes.delete('/api/member/admin/invites/:code', async (c) => {
  const code = normCode(c.req.param('code'))
  const res = await c.env.DB.prepare('DELETE FROM invite_codes WHERE code=? AND redeemed_by IS NULL').bind(code).run()
  if (!res.meta.changes) return c.json({ success: false, error: 'not found or already used' }, 404)
  return c.json({ success: true })
})

memberRoutes.put('/api/member/admin/members/:id', async (c) => {
  const id = Number(c.req.param('id'))
  const data = (await c.req.json().catch(() => ({}))) as Row
  const sets: string[] = []
  const binds: any[] = []
  if ('status' in data) {
    sets.push('status=?')
    binds.push(data.status === '정지' ? '정지' : '활성')
  }
  if ('nickname' in data) {
    sets.push('nickname=?')
    binds.push(String(data.nickname ?? '').trim().slice(0, 20) || null)
  }
  if (!sets.length) return c.json({ success: false, error: 'nothing to update' }, 400)
  binds.push(id)
  await c.env.DB.prepare(`UPDATE members SET ${sets.join(', ')} WHERE id=?`).bind(...binds).run()
  const row = await c.env.DB.prepare(`SELECT ${PUBLIC_FIELDS} FROM members WHERE id=?`).bind(id).first<Row>()
  if (!row) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true, member: row })
})


/** 손님들이 남긴 감상 모아보기 — 관리자만 본다 (손님에게는 서로 안 보인다) */
memberRoutes.get('/api/member/admin/notes', async (c) => {
  const { results } = await c.env.DB
    .prepare(
      'SELECT n.bean_id AS bean_id, n.rating AS rating, n.body AS body, n.updated_at AS updated_at, ' +
        'u.unlocked_at AS tasted_at, m.id AS member_id, m.nickname AS nickname, m.name AS name, m.email AS email ' +
        'FROM bean_notes n JOIN members m ON m.id = n.member_id ' +
        'LEFT JOIN bean_unlocks u ON u.member_id = n.member_id AND u.bean_id = n.bean_id ' +
        'ORDER BY n.updated_at DESC LIMIT 300',
    )
    .all<Row>()
  return c.json({
    success: true,
    items: results.map((r) => ({ ...r, bean_name: beanById(String(r.bean_id))?.name_ko ?? String(r.bean_id) })),
  })
})
