// cafe-coffee Worker — Flask app.py 포팅 (docs/CLOUDFLARE-MIGRATION.md Phase 2)
// 불변 조건: 한글 JSON 키, {start,end} 날짜 객체, {success,...} 응답 형태를 Flask와 동일하게 유지.
import { Hono } from 'hono'
import { Env, Row, getCookie, utcNowISO } from './util'
import { adminRoutes } from './auth'
import { coffeeRoutes } from './coffee'
import { beanRoutes } from './beans'
import { nearbyRoutes } from './nearby'
import versionJson from '../../cafe-coffee-apk/www/version.json'

const app = new Hono<{ Bindings: Env }>()

// ---------- 방문자 추적 (app.py _track_visit — 쿠키 기반, 봇 제외) ----------

const VISIT_COOKIE = 'vid'
const VISIT_COOKIE_TTL = 86400
const BOT_RE = /bot|crawler|spider|crawl|http:\/\/|googlebot|bingbot|yandex|duckduck|baiduspider|slurp|facebookexternalhit|whatsapp|telegrambot|applebot|amazonbot|petalbot|semrushbot|ahrefsbot|mj12bot|headlesschrome|phantomjs|puppeteer|playwright|selenium/i
const TRACK_PATH_RE = /^\/(?:$|insight(?:\/|$)|apk(?:\/|$)|game(?:-apk)?(?:\/|$)|today(?:\/|$)|roastery(?:\/|$))/
const VID_RE = /^[A-Za-z0-9_-]{8,40}$/

function classifyDevice(ua: string): string {
  const l = (ua || '').toLowerCase()
  if (!l) return 'desktop'
  if (BOT_RE.test(l)) return 'bot'
  if (l.includes('ipad') || (l.includes('android') && !l.includes('mobile'))) return 'tablet'
  if (['mobile', 'iphone', 'ipod', 'android'].some((s) => l.includes(s))) return 'mobile'
  return 'desktop'
}

app.use('*', async (c, next) => {
  let setVid: string | null = null
  if (c.req.method === 'GET' && TRACK_PATH_RE.test(new URL(c.req.url).pathname)) {
    const device = classifyDevice(c.req.header('User-Agent') || '')
    if (device !== 'bot') {
      let vid = getCookie(c.req.raw, VISIT_COOKIE)
      let isNew = 0
      if (!VID_RE.test(vid)) {
        const bytes = new Uint8Array(12)
        crypto.getRandomValues(bytes)
        vid = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
        isNew = 1
        setVid = vid
      }
      const tsUtc = utcNowISO()
      const kst = new Date(Date.now() + 9 * 3600_000)
      const path = new URL(c.req.url).pathname
      // 통계는 보조 기능 — 실패해도 요청 본 흐름은 막지 않음 (waitUntil 비동기)
      c.executionCtx.waitUntil(
        c.env.DB
          .prepare('INSERT INTO visits (ts, date_kst, hour_kst, path, visitor_id, device, is_new) VALUES (?,?,?,?,?,?,?)')
          .bind(tsUtc, kst.toISOString().slice(0, 10), kst.getUTCHours(), path, vid, device, isNew)
          .run()
          .catch(() => {}),
      )
    }
  }
  await next()
  if (setVid)
    c.header(
      'Set-Cookie',
      `${VISIT_COOKIE}=${setVid}; Max-Age=${VISIT_COOKIE_TTL}; Path=/; HttpOnly; SameSite=Lax; Secure`,
      { append: true },
    )
})

// ---------- API 라우터 ----------

app.route('/', adminRoutes)
app.route('/', coffeeRoutes)
app.route('/', nearbyRoutes) // beans보다 먼저 — /api/nearby/* 를 beans 의 use('/api/*') 가드보다 우선 매칭
app.route('/', beanRoutes)

// ---------- 인사이트 (정적 자산 기반 — app.py 1228~1320) ----------

const INSIGHT_ID_RE = /^[A-Za-z0-9][A-Za-z0-9\-]{0,127}$/
const INSIGHT_DATE_RE = /^\d{4}-\d{2}-\d{2}$/

async function fetchAssetJSON(c: any, path: string): Promise<any | null> {
  const res = await c.env.ASSETS.fetch(new Request(new URL(path, c.req.url)))
  if (!res.ok) return null
  try { return await res.json() } catch { return null }
}

app.get('/api/insights', async (c) => {
  const index = (await fetchAssetJSON(c, '/static/insights/index.json')) || {}
  let items: any[] = index.items || []
  items = [...items].sort((a, b) => {
    const ka = `${a.date || ''}|${a.id || ''}`
    const kb = `${b.date || ''}|${b.id || ''}`
    return ka < kb ? 1 : ka > kb ? -1 : 0
  })
  const limit = parseInt(c.req.query('limit') || '0', 10) || 0
  if (limit > 0) items = items.slice(0, limit)
  return c.json({ success: true, items, updated_at: index.updated_at ?? null })
})

app.get('/api/insights/:id', async (c) => {
  const id = c.req.param('id')
  if (!INSIGHT_ID_RE.test(id)) return c.json({ success: false, error: 'invalid id' }, 404)
  const data = await fetchAssetJSON(c, `/static/insights/${id}.json`)
  if (!data) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true, item: data })
})

// ---------- 수요책 Shorts (app.py 1134~1225 — YouTube RSS 프록시 + 캐시) ----------

const SUYOCHEK_FEED_URL = 'https://www.youtube.com/feeds/videos.xml?channel_id=UC1OMiatCVGDGzjgiZyaM1Tg'
const SUYOCHEK_TITLE_RE = /커피\s*마시러\s*가는\s*길/
const SUYOCHEK_EP_RE = /\((\d+)\s*회\)/
const SUYOCHEK_MAX_ITEMS = 50
const SUYOCHEK_SUPPLEMENT = [
  { id: '6V5H2D3Vg0Y', title: '커피 마시러 가는 길(116회) — 보조', ep: 116 },
  { id: 'cyJ8rWRIa4Q', title: '커피 마시러 가는 길(115회) — 보조', ep: 115 },
  { id: '5ClREy_mKrM', title: '커피 마시러 가는 길(114회) — 보조', ep: 114 },
]

function parseSuyochekFeed(xml: string) {
  const items: { id: string; title: string; ep: number | null }[] = []
  const entryRe = /<entry>([\s\S]*?)<\/entry>/g
  let m: RegExpExecArray | null
  while ((m = entryRe.exec(xml)) && items.length < SUYOCHEK_MAX_ITEMS) {
    const vid = (m[1].match(/<yt:videoId>([^<]+)<\/yt:videoId>/) || [])[1]?.trim()
    const title = (m[1].match(/<title>([^<]*)<\/title>/) || [])[1]?.trim()
    if (!vid || !title || !SUYOCHEK_TITLE_RE.test(title)) continue
    const epM = title.match(SUYOCHEK_EP_RE)
    items.push({ id: vid, title, ep: epM ? parseInt(epM[1], 10) : null })
  }
  return items
}

function mergeWithSupplement(rssItems: { id: string; title: string; ep: number | null }[]) {
  const seen = new Set(rssItems.map((it) => it.id))
  const merged = [...rssItems]
  for (const sup of SUYOCHEK_SUPPLEMENT) {
    if (seen.has(sup.id)) continue
    merged.push({ ...sup })
    seen.add(sup.id)
  }
  return merged.slice(0, SUYOCHEK_MAX_ITEMS)
}

app.get('/api/suyochek-shorts', async (c) => {
  // Workers Cache API 로 10분 캐시 (Flask 메모리 캐시 대응)
  const cacheKey = new Request('https://cache.internal/suyochek-shorts')
  const cache = caches.default
  const hit = await cache.match(cacheKey)
  if (hit) return new Response(hit.body, hit)
  let items = mergeWithSupplement([])
  try {
    const r = await fetch(SUYOCHEK_FEED_URL, {
      headers: { 'User-Agent': 'cafe-today-coffee/1.0 (+https://92cafe.co.kr)' },
      signal: AbortSignal.timeout(6000),
    })
    if (r.ok) items = mergeWithSupplement(parseSuyochekFeed(await r.text()))
  } catch { /* 폴백: 보조 목록 */ }
  const resp = c.json({ success: true, items, updated_at: Date.now() / 1000 })
  resp.headers.set('Cache-Control', 'public, max-age=600')
  c.executionCtx.waitUntil(cache.put(cacheKey, resp.clone()))
  return resp
})

// ---------- 앱 버전 ----------

app.get('/api/app-version', (c) => c.json({ build: null, ...versionJson }))

// ---------- 아직 포팅 안 된 API가 남았다면 명시적으로 ----------

app.all('/api/*', (c) => c.json({ success: false, error: `not yet ported: ${new URL(c.req.url).pathname}` }, 501))

// ---------- 페이지 라우트 (app.py 정적 페이지 매핑) ----------

const serveAsset = (path: string) => async (c: any) =>
  c.env.ASSETS.fetch(new Request(new URL(path, c.req.url), { headers: c.req.raw.headers }))

app.get('/', serveAsset('/static/roastery.html'))
app.get('/today', serveAsset('/index.html'))
app.get('/admin', serveAsset('/static/admin.html'))
app.get('/roastery', serveAsset('/static/roastery.html'))
app.get('/apk', serveAsset('/static/apk.html'))
app.get('/game', serveAsset('/static/game.html'))
app.get('/game-apk', serveAsset('/static/game-apk.html'))
app.get('/insight', serveAsset('/static/insight-list.html'))

// /insight/<id> — 풀 슬러그 → HTML, 날짜만 → index.json 해석 (app.py insight_article_page)
app.get('/insight/:id', async (c) => {
  const id = c.req.param('id')
  if (!INSIGHT_ID_RE.test(id)) return c.json({ success: false, error: 'invalid id' }, 404)
  const direct = await c.env.ASSETS.fetch(new Request(new URL(`/static/insights/${id}.html`, c.req.url)))
  if (direct.ok) return direct
  if (INSIGHT_DATE_RE.test(id)) {
    const index = (await fetchAssetJSON(c, '/static/insights/index.json')) || {}
    const matches = (index.items || []).filter((x: any) => x.date === id)
    if (matches.length === 1 && matches[0].id) {
      const res = await c.env.ASSETS.fetch(new Request(new URL(`/static/insights/${matches[0].id}.html`, c.req.url)))
      if (res.ok) return res
    } else if (matches.length > 1) {
      return c.redirect(`/insight?date=${id}`, 302)
    }
  }
  return c.json({ success: false, error: 'not found' }, 404)
})

// APK 다운로드 — GitHub Releases(apk-latest 태그)로 리다이렉트 (Phase 4)
// 구 경로 /downloads/*, /static/downloads/* 둘 다 지원 (apk.html 링크 호환)
const APK_RELEASE_BASE = 'https://github.com/alexyun78/cafe-coffee-today/releases/download/apk-latest/'
const downloadRedirect = (c: any) => {
  const name = new URL(c.req.url).pathname.split('/').pop() || ''
  if (!/^[A-Za-z0-9._-]+$/.test(name)) return c.json({ success: false, error: 'not found' }, 404)
  return c.redirect(APK_RELEASE_BASE + name, 302)
}
app.get('/downloads/:name', downloadRedirect)
app.get('/static/downloads/:name', downloadRedirect)

// 나머지는 정적 자산으로 (+ 비공개 관리자 별칭 경로 — 서버 .env 의 ADMIN_ALIAS_PATH 대응)
app.notFound((c) => {
  const alias = (c.env.ADMIN_ALIAS_PATH || '').trim()
  if (alias && alias.startsWith('/') && alias !== '/admin' && new URL(c.req.url).pathname === alias)
    return c.env.ASSETS.fetch(new Request(new URL('/static/admin.html', c.req.url)))
  return c.env.ASSETS.fetch(c.req.raw)
})

export default app
