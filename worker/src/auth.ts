// 관리자 인증 — app.py 194~305 포팅.
// Flask 세션 쿠키 → HMAC 서명 쿠키('adm')로 대체. Bearer 토큰(APK용)은 동일 개념 유지.
import { Hono } from 'hono'
import type { Context } from 'hono'
import { Env, clientIp, signToken, verifyToken, getCookie } from './util'

export const ADMIN_TOKEN_TTL_SEC = 60 * 60 * 24 * 7 // 7일
const ADMIN_TOKEN_SALT = 'admin-token-v1'
const ADMIN_COOKIE = 'adm'

const PIN_MAX_ATTEMPTS = 5
const PIN_WINDOW_SEC = 300
const PIN_LOCK_SEC = 900

type C = Context<{ Bindings: Env }>

export async function isAdminAuthed(c: C): Promise<boolean> {
  const secret = c.env.SESSION_SECRET
  const cookieTok = getCookie(c.req.raw, ADMIN_COOKIE)
  if (cookieTok && (await verifyToken(secret, ADMIN_TOKEN_SALT, cookieTok, ADMIN_TOKEN_TTL_SEC))?.admin)
    return true
  const auth = c.req.header('Authorization') || ''
  if (auth.startsWith('Bearer ')) {
    const tok = auth.slice(7).trim()
    if (tok && (await verifyToken(secret, ADMIN_TOKEN_SALT, tok, ADMIN_TOKEN_TTL_SEC))?.admin) return true
  }
  return false
}

/** @require_pin 미들웨어 */
export async function requirePin(c: C, next: () => Promise<void>) {
  if (!(await isAdminAuthed(c))) return c.json({ success: false, error: 'unauthorized' }, 401)
  await next()
}

// ---- PIN brute-force 카운터 (D1 pin_attempts — db.py pin_*) ----

async function pinCheckLock(db: D1Database, ip: string): Promise<number> {
  const now = Date.now() / 1000
  const row = await db.prepare('SELECT locked_until FROM pin_attempts WHERE ip=?').bind(ip).first<any>()
  if (row && row.locked_until > now) return Math.floor(row.locked_until - now)
  return 0
}

async function pinRecordFailure(db: D1Database, ip: string): Promise<[number, number]> {
  const now = Date.now() / 1000
  const row = await db.prepare('SELECT count, window_start FROM pin_attempts WHERE ip=?').bind(ip).first<any>()
  let count: number, windowStart: number
  if (!row || now - row.window_start > PIN_WINDOW_SEC) {
    count = 1
    windowStart = now
  } else {
    count = row.count + 1
    windowStart = row.window_start
  }
  const lockedUntil = count >= PIN_MAX_ATTEMPTS ? now + PIN_LOCK_SEC : 0
  await db
    .prepare(
      'INSERT INTO pin_attempts(ip, count, window_start, locked_until) VALUES(?,?,?,?) ' +
        'ON CONFLICT(ip) DO UPDATE SET count=excluded.count, window_start=excluded.window_start, ' +
        'locked_until=excluded.locked_until',
    )
    .bind(ip, count, windowStart, lockedUntil)
    .run()
  return [count, Math.max(0, Math.floor(lockedUntil - now))]
}

function admCookie(value: string, maxAge: number): string {
  return `${ADMIN_COOKIE}=${value}; Max-Age=${maxAge}; Path=/; HttpOnly; SameSite=Lax; Secure`
}

export const adminRoutes = new Hono<{ Bindings: Env }>()

adminRoutes.post('/api/admin/verify', async (c) => {
  const ip = clientIp(c.req.raw)
  const locked = await pinCheckLock(c.env.DB, ip)
  if (locked)
    return c.json({ success: false, error: 'locked', retry_after: locked, max_attempts: PIN_MAX_ATTEMPTS }, 429)

  const data = (await c.req.json().catch(() => ({}))) as any
  const pin = String(data.pin || '').trim()
  if (pin && pin === c.env.ADMIN_PIN) {
    await c.env.DB.prepare('DELETE FROM pin_attempts WHERE ip=?').bind(ip).run()
    const token = await signToken(c.env.SESSION_SECRET, 'admin-token-v1', { admin: true })
    c.header('Set-Cookie', admCookie(token, ADMIN_TOKEN_TTL_SEC))
    return c.json({ success: true, token })
  }

  const [count, lockRemaining] = await pinRecordFailure(c.env.DB, ip)
  await new Promise((r) => setTimeout(r, 400)) // 타이밍 공격/스크립트 속도 저하
  if (lockRemaining)
    return c.json(
      { success: false, error: 'locked', retry_after: lockRemaining, max_attempts: PIN_MAX_ATTEMPTS },
      429,
    )
  return c.json(
    {
      success: false,
      error: 'invalid pin',
      attempts_left: Math.max(0, PIN_MAX_ATTEMPTS - count),
      max_attempts: PIN_MAX_ATTEMPTS,
    },
    401,
  )
})

adminRoutes.post('/api/admin/logout', (c) => {
  c.header('Set-Cookie', admCookie('', 0))
  return c.json({ success: true })
})

adminRoutes.get('/api/admin/status', async (c) =>
  c.json({ success: true, authenticated: await isAdminAuthed(c) }))

// GET /api/admin/stats — 방문자 통계 (db.py stats_summary)
adminRoutes.get('/api/admin/stats', requirePin, async (c) => {
  const db = c.env.DB
  const todayKst = new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 10)
  const [tu, au, tp, ap, hourly, devices] = await db.batch([
    db.prepare('SELECT COUNT(DISTINCT visitor_id) AS c FROM visits WHERE date_kst=?').bind(todayKst),
    db.prepare('SELECT COUNT(DISTINCT visitor_id) AS c FROM visits'),
    db.prepare('SELECT COUNT(*) AS c FROM visits WHERE date_kst=?').bind(todayKst),
    db.prepare('SELECT COUNT(*) AS c FROM visits'),
    db.prepare('SELECT hour_kst, COUNT(DISTINCT visitor_id) AS c FROM visits WHERE date_kst=? GROUP BY hour_kst').bind(todayKst),
    db.prepare('SELECT device, COUNT(DISTINCT visitor_id) AS c FROM visits WHERE date_kst=? GROUP BY device').bind(todayKst),
  ])
  const hourlyMap: Record<number, number> = {}
  for (const r of hourly.results as any[]) hourlyMap[r.hour_kst] = r.c
  const devMap: Record<string, number> = {}
  for (const r of devices.results as any[]) devMap[r.device] = r.c
  return c.json({
    success: true,
    today_kst: todayKst,
    today_uniques: (tu.results[0] as any)?.c ?? 0,
    today_pv: (tp.results[0] as any)?.c ?? 0,
    total_uniques: (au.results[0] as any)?.c ?? 0,
    total_pv: (ap.results[0] as any)?.c ?? 0,
    hourly_kst: Array.from({ length: 24 }, (_, h) => ({ hour: h, count: hourlyMap[h] ?? 0 })),
    devices: devMap,
  })
})
