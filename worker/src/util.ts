// 공용 유틸 — db.py 헬퍼 포팅. 응답 형태는 Flask와 동일하게 유지.

export type Env = {
  DB: D1Database
  ASSETS: Fetcher
  ADMIN_PIN: string
  SESSION_SECRET: string // 구 FLASK_SECRET — 같은 값을 넣어 ip_hash 연속성 유지
  ADMIN_ALIAS_PATH?: string
  GITHUB_DISPATCH_TOKEN?: string // nearby 수집 워크플로 트리거용 (actions:write PAT)
}

export type Row = Record<string, any>

/** Notion 호환 날짜 객체 (db.py _date_obj) */
export const dateObj = (s: string | null | undefined) => (s ? { start: s, end: null } : null)

export const STATUS_ORDER: Record<string, number> = { 예정: 0, '진행 중': 1, 완료: 2 }

/** KST 오늘 날짜 — Flask 서버가 KST라 date.today() 대응 */
export function kstTodayISO(): string {
  return new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 10)
}

/** UTC 현재 시각 'YYYY-MM-DDTHH:MM:SSZ' (db.py _utc_now_iso) */
export function utcNowISO(): string {
  return new Date().toISOString().slice(0, 19) + 'Z'
}

/** 제공일 기준 상태 자동 진행 (db.py _compute_display_status) */
export function computeDisplayStatus(raw: string | null, serveDate: string | null): string | null {
  if (!serveDate) return raw
  const today = kstTodayISO()
  const natural = serveDate > today ? '예정' : serveDate === today ? '진행 중' : '완료'
  const rawKey = raw || '예정'
  return (STATUS_ORDER[natural] ?? 0) > (STATUS_ORDER[rawKey] ?? 0) ? natural : rawKey
}

/** 오늘 기준 N개월 전 — 월말 클램프 (db.py _months_ago_iso) */
export function monthsAgoISO(months: number): string {
  const t = new Date(Date.now() + 9 * 3600_000)
  let y = t.getUTCFullYear()
  let m = t.getUTCMonth() + 1 - months
  while (m < 1) { m += 12; y -= 1 }
  for (const d of [t.getUTCDate(), 28, 27, 26, 25]) {
    const cand = new Date(Date.UTC(y, m - 1, d))
    if (cand.getUTCMonth() === m - 1) return cand.toISOString().slice(0, 10)
  }
  return new Date(Date.UTC(y, m - 1, 1)).toISOString().slice(0, 10)
}

export const dateToTs = (s: string): number => {
  const t = Date.parse((s || '').slice(0, 10))
  return Number.isFinite(t) ? t : 0
}

/** 클라이언트 IP (Cloudflare 헤더) */
export function clientIp(req: Request): string {
  return (
    req.headers.get('CF-Connecting-IP') ||
    (req.headers.get('X-Forwarded-For') || '').split(',')[0].trim() ||
    'unknown'
  )
}

export async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

// --- base64url ---
export function b64urlEncode(bytes: Uint8Array): string {
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}
export function b64urlDecode(s: string): Uint8Array {
  const pad = s.length % 4 === 0 ? '' : '='.repeat(4 - (s.length % 4))
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/') + pad)
  return Uint8Array.from(bin, (c) => c.charCodeAt(0))
}

const enc = new TextEncoder()

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, [
    'sign',
    'verify',
  ])
}

/** salt 구분 HMAC 서명 토큰 발급: payloadB64.sigB64 (iat 포함 → TTL 검증) */
export async function signToken(secret: string, salt: string, payload: Row): Promise<string> {
  const body = b64urlEncode(enc.encode(JSON.stringify({ ...payload, iat: Math.floor(Date.now() / 1000) })))
  const key = await hmacKey(secret)
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(`${salt}.${body}`))
  return `${body}.${b64urlEncode(new Uint8Array(sig))}`
}

/** 토큰 검증 — 유효하면 payload, 아니면 null */
export async function verifyToken(
  secret: string, salt: string, token: string, maxAgeSec: number,
): Promise<Row | null> {
  const parts = (token || '').split('.')
  if (parts.length !== 2) return null
  const [body, sig] = parts
  try {
    const key = await hmacKey(secret)
    const ok = await crypto.subtle.verify('HMAC', key, b64urlDecode(sig) as BufferSource, enc.encode(`${salt}.${body}`))
    if (!ok) return null
    const payload = JSON.parse(new TextDecoder().decode(b64urlDecode(body)))
    if (typeof payload.iat !== 'number') return null
    if (Math.floor(Date.now() / 1000) - payload.iat > maxAgeSec) return null
    return payload
  } catch {
    return null
  }
}

export function getCookie(req: Request, name: string): string {
  const m = (req.headers.get('Cookie') || '').match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`))
  return m ? decodeURIComponent(m[1]) : ''
}
