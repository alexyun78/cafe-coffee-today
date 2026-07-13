// cafe-coffee Worker — Flask app.py 포팅 (docs/CLOUDFLARE-MIGRATION.md Phase 2)
// 불변 조건: 한글 JSON 키, {start,end} 날짜 객체, {success,...} 응답 형태를 Flask와 동일하게 유지.
import { Hono } from 'hono'

type Env = {
  DB: D1Database
  ASSETS: Fetcher
  // secrets (wrangler secret put): ADMIN_PIN, SESSION_SECRET, ADMIN_ALIAS_PATH?
}

const app = new Hono<{ Bindings: Env }>()

// ---------- 유틸 (db.py 포팅) ----------

/** Notion 호환 날짜 객체 (db.py _date_obj) */
const dateObj = (s: string | null | undefined) => (s ? { start: s, end: null } : null)

const STATUS_ORDER: Record<string, number> = { 예정: 0, '진행 중': 1, 완료: 2 }

/** KST 오늘 날짜 (서버가 KST였으므로 date.today() 대응) */
function kstTodayISO(): string {
  return new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 10)
}

/** 제공일 기준 상태 자동 진행 (db.py _compute_display_status) */
function computeDisplayStatus(raw: string | null, serveDate: string | null): string | null {
  if (!serveDate) return raw
  const today = kstTodayISO()
  const natural = serveDate > today ? '예정' : serveDate === today ? '진행 중' : '완료'
  const rawKey = raw || '예정'
  const rawO = STATUS_ORDER[rawKey] ?? 0
  const natO = STATUS_ORDER[natural] ?? 0
  return natO > rawO ? natural : rawKey
}

/** 컵노트 단일 소스 SQL (db.py _EFF_CUP_NOTES_SQL) */
const EFF_CUP_NOTES_SQL = `COALESCE(
  (SELECT gb.cup_notes FROM green_beans gb
    WHERE gb.id = c.green_bean_id AND TRIM(COALESCE(gb.cup_notes,'')) <> ''),
  (SELECT gb.cup_notes FROM green_beans gb
    WHERE gb.name = c.name AND TRIM(COALESCE(gb.cup_notes,'')) <> ''
    ORDER BY gb.id LIMIT 1)
) AS bean_cup_notes`

type CoffeeRow = Record<string, any>

/** DB row → 한글 키 API 응답 (db.py _row_to_api) */
function rowToApi(row: CoffeeRow) {
  let cup = row.cup_notes
  if (row.bean_cup_notes != null && String(row.bean_cup_notes).trim()) cup = row.bean_cup_notes
  return {
    id: row.id,
    커피: row.name,
    로스터리: row.roastery,
    로스팅: dateObj(row.roast_date),
    프로세싱: row.process,
    상태: computeDisplayStatus(row.status, row.serve_date),
    컵노트: cup,
    감상: row.comment,
    제공일: dateObj(row.serve_date),
    구분: row.category,
    'BREWED AT': row.brewed_at,
    '로스팅 포인트': row.roast_point,
    운영상태: row.availability || '운영',
  }
}

/** 오늘 기준 N개월 전 (db.py _months_ago_iso — 월말 클램프 동일) */
function monthsAgoISO(months: number): string {
  const t = new Date(Date.now() + 9 * 3600_000) // KST
  let y = t.getUTCFullYear()
  let m = t.getUTCMonth() + 1 - months
  while (m < 1) { m += 12; y -= 1 }
  for (const d of [t.getUTCDate(), 28, 27, 26, 25]) {
    const cand = new Date(Date.UTC(y, m - 1, d))
    if (cand.getUTCMonth() === m - 1) {
      return cand.toISOString().slice(0, 10)
    }
  }
  return new Date(Date.UTC(y, m - 1, 1)).toISOString().slice(0, 10)
}

const dateToTs = (s: string): number => {
  const t = Date.parse((s || '').slice(0, 10))
  return Number.isFinite(t) ? t : 0
}

/** 제공 중 디카페인 (db.py get_current_decaf) */
async function getCurrentDecaf(db: D1Database) {
  const s = await db
    .prepare("SELECT value FROM settings WHERE key='current_decaf_gb_id'")
    .first<{ value: string }>()
  if (!s || !s.value) return null
  const id = parseInt(s.value, 10)
  if (!Number.isFinite(id)) return null
  const bean = await db
    .prepare('SELECT id, name, process, cup_notes, is_decaf FROM green_beans WHERE id = ?')
    .bind(id)
    .first<CoffeeRow>()
  if (!bean || !bean.is_decaf) return null
  return { id: bean.id, name: bean.name, process: bean.process, cup_notes: bean.cup_notes }
}

// ---------- 공개 조회 ----------

// GET /api/coffee — {today, history, decaf} (app.py get_coffee + db.py list_today_and_history)
app.get('/api/coffee', async (c) => {
  try {
    const { results } = await c.env.DB
      .prepare(`SELECT c.*, ${EFF_CUP_NOTES_SQL} FROM coffees c`)
      .all<CoffeeRow>()

    const cutoff = monthsAgoISO(3)
    const todayISO = kstTodayISO()
    const today: any[] = []
    const history: any[] = []

    for (const row of results) {
      const item = rowToApi(row)
      if (!item['커피']) continue
      const status = item['상태']
      if (status === '진행 중') {
        today.push(item)
        history.push(item)
      } else if (status === '예정') {
        history.push(item)
      } else if (status === '완료') {
        const serve = item['제공일']?.start || ''
        const roast = item['로스팅']?.start || ''
        const ref = serve || roast
        if (ref && ref >= cutoff) history.push(item)
      }
    }

    // 정렬: 진행중 → 예정(가까운 제공일순) → 그 외(로스팅 최신순), 동률은 이름순
    const sortKey = (item: any): [number, number, string] => {
      const status = item['상태']
      const serve = item['제공일']?.start || ''
      const roast = item['로스팅']?.start || ''
      const name = item['커피'] || ''
      if (status === '진행 중') return [0, -dateToTs(roast), name]
      if (status === '예정' && serve && serve >= todayISO) return [1, dateToTs(serve), name]
      return [2, -dateToTs(roast), name]
    }
    history.sort((a, b) => {
      const ka = sortKey(a), kb = sortKey(b)
      if (ka[0] !== kb[0]) return ka[0] - kb[0]
      if (ka[1] !== kb[1]) return ka[1] - kb[1]
      return ka[2] < kb[2] ? -1 : ka[2] > kb[2] ? 1 : 0
    })

    return c.json({ success: true, today, history, decaf: await getCurrentDecaf(c.env.DB) })
  } catch (e: any) {
    return c.json({ success: false, error: String(e?.message || e) }, 500)
  }
})

// ---------- 인사이트 (정적 자산 기반 — app.py api_insights_*) ----------

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

// ---------- 앱 버전 ----------

app.get('/api/app-version', async (c) => {
  // TODO(Phase 4): version.json 값 반영 + build를 Workers Builds 커밋 SHA로
  return c.json({ version: '1.3.0', build: null })
})

// ---------- 카드 PNG (마이그레이션 결정: 보류) ----------

app.post('/api/coffee/:id/card-token', (c) =>
  c.json({ success: false, error: 'card download not available (migration)' }, 501))
app.get('/api/coffee/:id/card.png', (c) =>
  c.json({ success: false, error: 'card download not available (migration)' }, 501))

// ---------- 아직 포팅 안 된 API (Phase 2 진행 중) ----------

app.all('/api/*', (c) =>
  c.json({ success: false, error: `not yet ported: ${new URL(c.req.url).pathname}` }, 501))

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

// /insight/<id> — 풀 슬러그 → 해당 HTML, 날짜만 → index.json에서 해석 (app.py insight_article_page)
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

// /downloads/* — APK 배포는 GitHub Releases로 이전 예정 (Phase 4)
app.get('/downloads/*', (c) =>
  c.json({ success: false, error: 'downloads moved (migration in progress)' }, 404))

// 나머지는 정적 자산으로
app.notFound((c) => c.env.ASSETS.fetch(c.req.raw))

export default app
