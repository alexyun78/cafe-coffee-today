// 주변 가게 리뷰 모니터링 — app.py 1015~1091 + db.py nearby_* 포팅.
// 수집 자체는 GitHub Actions(collect_nearby.py)에서 실행하고 결과를
// POST /api/nearby/ingest 로 전송한다 (Workers에서 네이버 스크래핑 불가/부적합).
import { Hono } from 'hono'
import { Env, Row, utcNowISO } from './util'
import { requirePin } from './auth'

export const nearbyRoutes = new Hono<{ Bindings: Env }>()
// 관리자 전용 가드 — nearby 경로에만 정확히 적용 (블랭킷 use('/api/*') 금지)
// ingest/collect-targets 도 관리자 토큰(Bearer) 필요 — GH Actions 는 ADMIN_PIN 으로
// /api/admin/verify 를 호출해 토큰을 받은 뒤 사용한다.
nearbyRoutes.use('/api/nearby/*', requirePin)

nearbyRoutes.get('/api/nearby/overview', async (c) => {
  const db = c.env.DB
  const includeHidden = c.req.query('include_hidden') === '1'
  const where = includeHidden ? '' : 'WHERE s.hidden = 0'
  const shops = (
    await db
      .prepare(
        `SELECT s.*,
             (SELECT COUNT(*) FROM nearby_reviews r WHERE r.shop_id = s.id) AS sample_count,
             (SELECT MAX(visited_date) FROM nearby_reviews r WHERE r.shop_id = s.id) AS last_review_date
         FROM nearby_shops s ${where}
         ORDER BY s.dist_m ASC, s.name ASC`,
      )
      .all<Row>()
  ).results
  // 최신/직전 스냅샷 2건씩 — 가게별 쿼리를 batch 로 한 번에
  const snapStmts = shops.map((s) =>
    db
      .prepare(
        'SELECT fetched_date, visitor_count, blog_count, visitor_score FROM nearby_review_counts ' +
          'WHERE shop_id=? ORDER BY fetched_date DESC LIMIT 2',
      )
      .bind(s.id),
  )
  if (snapStmts.length) {
    const snapResults = await db.batch(snapStmts)
    shops.forEach((s, i) => {
      const snaps = snapResults[i].results as Row[]
      s.counts = snaps[0] ?? null
      s.counts_prev = snaps[1] ?? null
    })
  }
  const run = await db.prepare('SELECT * FROM nearby_collect_runs ORDER BY id DESC LIMIT 1').first<Row>()
  return c.json({ success: true, shops, last_run: run ?? null })
})

nearbyRoutes.get('/api/nearby/shops/:id{[0-9]+}/reviews', async (c) => {
  const { results } = await c.env.DB
    .prepare(
      'SELECT id, source, visited_date, body, author, url, first_seen_at FROM nearby_reviews ' +
        'WHERE shop_id=? ORDER BY (visited_date IS NULL), visited_date DESC, id DESC LIMIT 50',
    )
    .bind(parseInt(c.req.param('id'), 10))
    .all<Row>()
  return c.json({ success: true, reviews: results })
})

// 성장 리포트 (db.py nearby_growth)
nearbyRoutes.get('/api/nearby/growth', async (c) => {
  const db = c.env.DB
  const shops = (
    await db.prepare('SELECT id, name, dist_m, is_anchor FROM nearby_shops WHERE hidden=0 ORDER BY dist_m').all<Row>()
  ).results
  const out: Row[] = []
  for (const s of shops) {
    const latest = await db
      .prepare(
        'SELECT fetched_date, visitor_count, blog_count, visitor_score FROM nearby_review_counts ' +
          'WHERE shop_id=? ORDER BY fetched_date DESC LIMIT 1',
      )
      .bind(s.id)
      .first<Row>()
    const dates = (
      await db
        .prepare(
          "SELECT visited_date FROM nearby_reviews WHERE shop_id=? AND source='visitor' " +
            'AND visited_date IS NOT NULL ORDER BY visited_date DESC LIMIT 10',
        )
        .bind(s.id)
        .all<Row>()
    ).results.map((r) => r.visited_date as string)
    let velWeek: number | null = null
    let spanDays: number | null = null
    if (dates.length >= 2) {
      const dNew = Date.parse(dates.reduce((a, b) => (a > b ? a : b)))
      const dOld = Date.parse(dates.reduce((a, b) => (a < b ? a : b)))
      if (Number.isFinite(dNew) && Number.isFinite(dOld)) {
        spanDays = Math.round((dNew - dOld) / 86400_000)
        if (spanDays > 0) velWeek = Math.round(((dates.length - 1) / spanDays) * 7 * 10) / 10
      }
    }
    const delta = async (days: number): Promise<Row | null> => {
      if (!latest) return null
      const target = new Date(Date.parse(latest.fetched_date) - days * 86400_000).toISOString().slice(0, 10)
      const base = await db
        .prepare(
          'SELECT fetched_date, visitor_count, blog_count FROM nearby_review_counts ' +
            'WHERE shop_id=? AND fetched_date<=? ORDER BY fetched_date DESC LIMIT 1',
        )
        .bind(s.id, target)
        .first<Row>()
      if (!base || base.visitor_count == null || latest.visitor_count == null) return null
      const realDays =
        Math.round((Date.parse(latest.fetched_date) - Date.parse(base.fetched_date)) / 86400_000) || 1
      return {
        base_date: base.fetched_date,
        days: realDays,
        dv: latest.visitor_count - base.visitor_count,
        db: (base.blog_count != null || latest.blog_count != null)
          ? (latest.blog_count || 0) - (base.blog_count || 0)
          : 0,
      }
    }
    out.push({
      ...s,
      fetched_date: latest?.fetched_date ?? null,
      visitor: latest?.visitor_count ?? null,
      blog: latest?.blog_count ?? null,
      rating: latest?.visitor_score ?? null,
      vel_week: velWeek,
      span_days: spanDays,
      sample_n: dates.length,
      delta7: await delta(7),
      delta30: await delta(30),
    })
  }
  const snapDays = await db.prepare('SELECT COUNT(DISTINCT fetched_date) AS n FROM nearby_review_counts').first<Row>()
  return c.json({ success: true, shops: out, snapshot_days: snapDays?.n ?? 0 })
})

nearbyRoutes.post('/api/nearby/shops', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  if (!String(data.name || '').trim()) return c.json({ success: false, error: 'name 필수' }, 400)
  try {
    const res = await c.env.DB
      .prepare(
        'INSERT INTO nearby_shops (name, category, road_address, dist_m, place_id, homepage, notes) VALUES (?,?,?,?,?,?,?)',
      )
      .bind(
        String(data.name).trim(), data.category ?? null, data.road_address ?? null,
        data.dist_m ?? null, String(data.place_id || '').trim() || null,
        data.homepage ?? null, data.notes ?? null,
      )
      .run()
    return c.json({ success: true, id: res.meta.last_row_id })
  } catch {
    return c.json({ success: false, error: '이미 있는 가게 이름입니다' }, 409)
  }
})

nearbyRoutes.put('/api/nearby/shops/:id{[0-9]+}', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  const allowed = ['name', 'category', 'road_address', 'dist_m', 'place_id', 'homepage', 'hidden', 'notes']
  const sets: string[] = []
  const vals: any[] = []
  for (const k of allowed)
    if (k in data) {
      let v = data[k]
      if (k === 'place_id') v = v != null ? String(v).trim() || null : null
      sets.push(`${k}=?`)
      vals.push(v)
    }
  if (!sets.length) return c.json({ success: false, error: 'not found' }, 404)
  sets.push("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
  vals.push(parseInt(c.req.param('id'), 10))
  const res = await c.env.DB.prepare(`UPDATE nearby_shops SET ${sets.join(',')} WHERE id=?`).bind(...vals).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

nearbyRoutes.delete('/api/nearby/shops/:id{[0-9]+}', async (c) => {
  const res = await c.env.DB.prepare('DELETE FROM nearby_shops WHERE id=?').bind(parseInt(c.req.param('id'), 10)).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

// 수동 수집 트리거 — GitHub Actions workflow_dispatch (Phase 3에서 워크플로 추가)
nearbyRoutes.post('/api/nearby/refresh', async (c) => {
  const inProgress = await c.env.DB
    .prepare(
      'SELECT 1 FROM nearby_collect_runs WHERE finished_at IS NULL ' +
        "AND started_at > strftime('%Y-%m-%dT%H:%M:%SZ','now','-30 minutes') LIMIT 1",
    )
    .first()
  if (inProgress) return c.json({ success: false, error: '이미 수집이 진행 중입니다' }, 409)
  if (!c.env.GITHUB_DISPATCH_TOKEN)
    return c.json({ success: false, error: '수집 트리거 미설정 (GITHUB_DISPATCH_TOKEN)' }, 501)
  const resp = await fetch(
    'https://api.github.com/repos/alexyun78/cafe-coffee-today/actions/workflows/nearby-collect.yml/dispatches',
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${c.env.GITHUB_DISPATCH_TOKEN}`,
        Accept: 'application/vnd.github+json',
        'User-Agent': 'cafe-coffee-worker',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main' }),
    },
  )
  if (resp.status !== 204)
    return c.json({ success: false, error: `트리거 실패 (${resp.status})` }, 502)
  return c.json({ success: true, started: true })
})

// ---------- 수집 결과 인제스트 (GitHub Actions collect_nearby.py 가 호출) ----------
// 바디: { run: {started_at, ok, message},
//         counts: [{shop_id, fetched_date, visitor_count, blog_count, visitor_score}],
//         reviews: [{shop_id, source, visited_date, body, author, url, review_hash}],
//         keywords: [{shop_id, keywords_json}] }
nearbyRoutes.post('/api/nearby/ingest', async (c) => {
  const data = (await c.req.json().catch(() => null)) as Row | null
  if (!data) return c.json({ success: false, error: 'invalid body' }, 400)
  const db = c.env.DB
  const stmts: D1PreparedStatement[] = []
  for (const r of data.counts || [])
    stmts.push(
      db
        .prepare(
          'INSERT INTO nearby_review_counts (shop_id, fetched_date, visitor_count, blog_count, visitor_score) ' +
            'VALUES (?,?,?,?,?) ON CONFLICT(shop_id, fetched_date) DO UPDATE SET ' +
            'visitor_count=excluded.visitor_count, blog_count=excluded.blog_count, visitor_score=excluded.visitor_score',
        )
        .bind(r.shop_id, r.fetched_date, r.visitor_count ?? null, r.blog_count ?? null, r.visitor_score ?? null),
    )
  for (const r of data.reviews || [])
    stmts.push(
      db
        .prepare(
          'INSERT OR IGNORE INTO nearby_reviews (shop_id, source, visited_date, body, author, url, review_hash) ' +
            'VALUES (?,?,?,?,?,?,?)',
        )
        .bind(r.shop_id, r.source || 'naver', r.visited_date ?? null, r.body ?? null, r.author ?? null, r.url ?? null, r.review_hash),
    )
  for (const r of data.keywords || [])
    stmts.push(
      db
        .prepare(
          "UPDATE nearby_shops SET keywords_json=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
        )
        .bind(r.keywords_json, r.shop_id),
    )
  if (data.run)
    stmts.push(
      db
        .prepare('INSERT INTO nearby_collect_runs (started_at, finished_at, ok, message) VALUES (?,?,?,?)')
        .bind(data.run.started_at || utcNowISO(), utcNowISO(), data.run.ok ? 1 : 0, data.run.message ?? null),
    )
  if (stmts.length) await db.batch(stmts)
  return c.json({ success: true, applied: stmts.length })
})

// 수집 대상 목록 (GitHub Actions 가 조회)
nearbyRoutes.get('/api/nearby/collect-targets', async (c) => {
  const { results } = await c.env.DB
    .prepare(
      "SELECT id, name, place_id FROM nearby_shops WHERE place_id IS NOT NULL AND TRIM(place_id) != '' ORDER BY dist_m",
    )
    .all<Row>()
  return c.json({ success: true, shops: results })
})
