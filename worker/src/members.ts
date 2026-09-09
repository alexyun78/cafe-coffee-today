// 92도씨 회원 — 시크릿 QR 초대 가입 + 구글 로그인 (docs/MEMBERS.md)
//
// 규칙 하나: **가입은 초대 코드가 있어야만 된다.** 매장에서 필터 커피를 낼 때 건네는
// QR 카드가 유일한 문이고, 한 번 쓴 코드는 소진된다. 로그인은 그 다음부터 코드 없이
// 구글 버튼만으로 된다.
//
// 세션은 관리자와 같은 HMAC 서명 쿠키(util.signToken)를 salt 만 바꿔 쓴다 — D1 에
// 세션 테이블을 두지 않는다. 스키마: scripts/members_schema.sql
import { Hono } from 'hono'
import type { Context } from 'hono'
import { Env, Row, utcNowISO, signToken, verifyToken, getCookie, b64urlDecode, b64urlEncode } from './util'
import { requirePin } from './auth'

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

type C = Context<MemberEnv>

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

/** 로그인한 회원 행. 비로그인이거나 정지된 계정이면 null */
export async function currentMember(c: C): Promise<Row | null> {
  const tok = getCookie(c.req.raw, MEMBER_COOKIE)
  if (!tok) return null
  const payload = await verifyToken(c.env.SESSION_SECRET, MEMBER_SALT, tok, MEMBER_TTL_SEC)
  const id = Number(payload?.mid)
  if (!id) return null
  const row = await c.env.DB.prepare(`SELECT ${PUBLIC_FIELDS} FROM members WHERE id=?`).bind(id).first<Row>()
  if (!row || row.status !== '활성') return null
  return row
}

/** 회원 전용 라우트 가드 — 2단계(정복 기록, 노트)에서 쓴다 */
export async function requireMember(c: C, next: () => Promise<void>) {
  const m = await currentMember(c)
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

// ---------- 구글 OAuth ----------

/** 리디렉션 URI 는 요청 오리진에서 만든다 — 구글 콘솔에 프로덕션과 로컬 둘 다 등록해야 한다 */
const redirectUri = (c: C) => new URL('/auth/google/callback', c.req.url).toString()

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
  const next = safeNext(st.next) || '/me'

  // 3) 기존 회원이면 그대로 로그인 (초대 코드는 소진하지 않는다)
  let member = await db.prepare('SELECT * FROM members WHERE google_sub=?').bind(sub).first<Row>()
  let created = false

  if (!member) {
    // 4) 신규는 초대 코드가 반드시 있어야 한다
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

    // 5) 코드 소진 — 조건부 UPDATE 라 같은 코드를 동시에 써도 한 명만 성공한다
    const claim = await db
      .prepare('UPDATE invite_codes SET redeemed_by=?, redeemed_at=? WHERE code=? AND redeemed_by IS NULL')
      .bind(member.id, now, invite)
      .run()
    if (!claim.meta.changes) {
      const taken = await db.prepare('SELECT redeemed_by FROM invite_codes WHERE code=?').bind(invite).first<Row>()
      if (Number(taken?.redeemed_by) !== Number(member.id)) {
        await db.prepare('DELETE FROM members WHERE id=?').bind(member.id).run()
        return fail('invite_used')
      }
    }
  } else {
    if (member.status !== '활성') return fail('suspended')
    // 구글 쪽 프로필이 바뀌었을 수 있으니 로그인할 때마다 갱신한다
    await db
      .prepare('UPDATE members SET email=?, name=?, picture=?, last_login_at=? WHERE id=?')
      .bind(idPayload.email ?? null, idPayload.name ?? null, idPayload.picture ?? null, now, member.id)
      .run()
  }

  const token = await signToken(c.env.SESSION_SECRET, MEMBER_SALT, { mid: member.id })
  c.header('Set-Cookie', cookieHeader(STATE_COOKIE, '', 0))
  c.header('Set-Cookie', cookieHeader(MEMBER_COOKIE, token, MEMBER_TTL_SEC), { append: true })
  return c.redirect(created ? '/me?welcome=1' : next, 302)
})

// ---------- 공개 API ----------

memberRoutes.get('/api/member/me', async (c) => {
  const m = await currentMember(c)
  return c.json({
    success: true,
    login_enabled: Boolean(c.env.GOOGLE_CLIENT_ID),
    member: m ? memberPublic(m) : null,
  })
})

memberRoutes.post('/api/member/logout', (c) => {
  c.header('Set-Cookie', cookieHeader(MEMBER_COOKIE, '', 0))
  return c.json({ success: true })
})

/** 가입 랜딩(/join/<code>)에서 코드가 살아 있는지 확인 */
memberRoutes.get('/api/member/invite/:code', async (c) => {
  const code = normCode(c.req.param('code'))
  const { state } = await checkInvite(c.env.DB, code)
  return c.json({
    success: true,
    valid: state === 'ok',
    state,
    code_pretty: CODE_RE.test(code) ? prettyCode(code) : '',
    login_enabled: Boolean(c.env.GOOGLE_CLIENT_ID),
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

// ---------- 관리자 API ----------

for (const p of ['/api/member/admin', '/api/member/admin/*']) memberRoutes.use(p, requirePin)

memberRoutes.get('/api/member/admin/overview', async (c) => {
  const db = c.env.DB
  const [members, invites, batches] = await db.batch([
    db.prepare(`SELECT ${PUBLIC_FIELDS} FROM members ORDER BY joined_at DESC LIMIT 500`),
    db.prepare(
      'SELECT COUNT(*) AS total, SUM(CASE WHEN redeemed_by IS NULL THEN 1 ELSE 0 END) AS unused FROM invite_codes',
    ),
    db.prepare(
      "SELECT COALESCE(batch,'(묶음 없음)') AS batch, COUNT(*) AS total, " +
        'SUM(CASE WHEN redeemed_by IS NULL THEN 1 ELSE 0 END) AS unused, MIN(created_at) AS created_at ' +
        'FROM invite_codes GROUP BY batch ORDER BY created_at DESC',
    ),
  ])
  const inv = (invites.results[0] as Row) || {}
  return c.json({
    success: true,
    members: members.results,
    invite_total: inv.total ?? 0,
    invite_unused: inv.unused ?? 0,
    batches: batches.results,
  })
})

/** 초대 코드 조회 — 인쇄 시트(/member-cards)가 읽는다 */
memberRoutes.get('/api/member/admin/invites', async (c) => {
  const batch = c.req.query('batch') || ''
  const onlyUnused = c.req.query('unused') !== '0'
  const where: string[] = []
  const binds: any[] = []
  if (batch) {
    where.push('batch=?')
    binds.push(batch)
  }
  if (onlyUnused) where.push('redeemed_by IS NULL')
  const sql =
    'SELECT code, batch, note, created_at, expires_at, redeemed_by, redeemed_at FROM invite_codes' +
    (where.length ? ` WHERE ${where.join(' AND ')}` : '') +
    ' ORDER BY created_at DESC, code LIMIT 500'
  const { results } = await c.env.DB.prepare(sql).bind(...binds).all<Row>()
  return c.json({ success: true, items: results.map((r) => ({ ...r, pretty: prettyCode(String(r.code)) })) })
})

/** 코드 발급 — 인쇄할 카드 수만큼 미리 찍어둔다 */
memberRoutes.post('/api/member/admin/invites', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  const count = Math.min(200, Math.max(1, Math.floor(Number(data.count) || 0)))
  const batch = String(data.batch ?? '').trim().slice(0, 40) || null
  const note = String(data.note ?? '').trim().slice(0, 200) || null
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
          'INSERT INTO invite_codes (code, batch, note, created_at, expires_at) VALUES (?,?,?,?,?) ' +
            'ON CONFLICT(code) DO NOTHING',
        )
        .bind(code, batch, note, now, expires),
    ),
  )
  return c.json({
    success: true,
    batch,
    count: codes.length,
    codes: codes.map((code) => ({ code, pretty: prettyCode(code) })),
  })
})

/** 아직 안 쓴 코드만 폐기할 수 있다 (이미 가입한 회원의 흔적은 남긴다) */
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
