// 오늘의 커피 — app.py 307~607 + db.py coffees/feedback/suggestions 포팅.
// 불변 조건: 한글 JSON 키, {start,end} 날짜 객체, {success,...} 응답 형태 동일 유지.
import { Hono } from 'hono'
import {
  Env, Row, dateObj, kstTodayISO, computeDisplayStatus, monthsAgoISO, dateToTs,
  clientIp, sha256Hex, utcNowISO,
} from './util'
import { requirePin, isAdminAuthed } from './auth'

/** 컵노트 단일 소스 SQL (db.py _EFF_CUP_NOTES_SQL) */
export const EFF_CUP_NOTES_SQL = `COALESCE(
  (SELECT gb.cup_notes FROM green_beans gb
    WHERE gb.id = c.green_bean_id AND TRIM(COALESCE(gb.cup_notes,'')) <> ''),
  (SELECT gb.cup_notes FROM green_beans gb
    WHERE gb.name = c.name AND TRIM(COALESCE(gb.cup_notes,'')) <> ''
    ORDER BY gb.id LIMIT 1)
) AS bean_cup_notes`

/** DB row → 한글 키 API 응답 (db.py _row_to_api) */
export function rowToApi(row: Row) {
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

export async function getById(db: D1Database, id: number): Promise<Row | null> {
  const row = await db
    .prepare(`SELECT c.*, ${EFF_CUP_NOTES_SQL} FROM coffees c WHERE c.id=?`)
    .bind(id)
    .first<Row>()
  return row ? rowToApi(row) : null
}

/** 제공 중 디카페인 (db.py get_current_decaf) */
export async function getCurrentDecaf(db: D1Database) {
  const s = await db
    .prepare("SELECT value FROM settings WHERE key='current_decaf_gb_id'")
    .first<{ value: string }>()
  if (!s || !s.value) return null
  const id = parseInt(s.value, 10)
  if (!Number.isFinite(id)) return null
  const bean = await db
    .prepare('SELECT id, name, process, cup_notes, is_decaf FROM green_beans WHERE id=?')
    .bind(id)
    .first<Row>()
  if (!bean || !bean.is_decaf) return null
  return { id: bean.id, name: bean.name, process: bean.process, cup_notes: bean.cup_notes }
}

/** 같은 이름의 '실질 활성' 커피 (db.py find_active_by_name) */
export async function findActiveByName(db: D1Database, name: string): Promise<Row | null> {
  if (!name) return null
  return db
    .prepare(
      "SELECT * FROM coffees WHERE name=? AND status IN ('예정','진행 중') " +
        "AND (serve_date IS NULL OR serve_date='' OR serve_date >= ?) ORDER BY id DESC LIMIT 1",
    )
    .bind(name, kstTodayISO())
    .first<Row>()
}

const COFFEE_FIELDS = [
  'name', 'roastery', 'roast_date', 'process', 'status', 'cup_notes', 'comment',
  'serve_date', 'category', 'brewed_at', 'roast_point', 'availability', 'notion_id', 'green_bean_id',
] as const

export async function createCoffee(db: D1Database, data: Row): Promise<number> {
  const fields = [...COFFEE_FIELDS]
  const res = await db
    .prepare(`INSERT INTO coffees (${fields.join(',')}) VALUES (${fields.map(() => '?').join(',')})`)
    .bind(...fields.map((f) => data[f] ?? null))
    .run()
  return res.meta.last_row_id as number
}

async function updateCoffee(db: D1Database, id: number, data: Row): Promise<boolean> {
  const allowed = COFFEE_FIELDS.filter((f) => f !== 'notion_id' && f !== 'green_bean_id')
  const sets = allowed.filter((k) => k in data)
  if (!sets.length) return false
  const sql =
    `UPDATE coffees SET ${sets.map((k) => `${k}=?`).join(',')},` +
    `updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?`
  const res = await db.prepare(sql).bind(...sets.map((k) => data[k] ?? null), id).run()
  return (res.meta.changes ?? 0) > 0
}

/** 컵노트 단일 소스 동기화 (db.py sync_bean_cup_notes_from_coffee) */
async function syncBeanCupNotes(db: D1Database, coffeeId: number, cupNotes: any): Promise<void> {
  if (cupNotes == null || !String(cupNotes).trim()) return
  const row = await db.prepare('SELECT green_bean_id, name FROM coffees WHERE id=?').bind(coffeeId).first<Row>()
  if (!row) return
  if (row.green_bean_id) {
    await db
      .prepare("UPDATE green_beans SET cup_notes=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?")
      .bind(cupNotes, row.green_bean_id)
      .run()
  } else if (row.name) {
    await db
      .prepare("UPDATE green_beans SET cup_notes=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE name=?")
      .bind(cupNotes, row.name)
      .run()
  }
}

async function completeOtherInProgress(db: D1Database, exceptId: number): Promise<void> {
  await db
    .prepare(
      "UPDATE coffees SET status='완료', updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') " +
        "WHERE status='진행 중' AND id<>?",
    )
    .bind(exceptId)
    .run()
}

/** API payload (한글 키 허용) → DB 컬럼 (app.py _parse_payload) */
function parsePayload(data: Row): Row {
  const pick = (...keys: string[]) => {
    for (const k of keys) {
      if (k in data && data[k] !== null && data[k] !== '') {
        let v = data[k]
        if (v && typeof v === 'object' && !Array.isArray(v)) v = v.start
        return v ?? null
      }
    }
    return null
  }
  const pickInt = (...keys: string[]) => {
    const v = pick(...keys)
    if (v == null) return null
    const n = parseInt(String(v), 10)
    return Number.isFinite(n) ? n : null
  }
  return {
    name: pick('name', '커피'),
    roastery: pick('roastery', '로스터리'),
    roast_date: pick('roast_date', '로스팅'),
    process: pick('process', '프로세싱'),
    status: pick('status', '상태'),
    cup_notes: pick('cup_notes', '컵노트'),
    comment: pick('comment', '감상'),
    serve_date: pick('serve_date', '제공일'),
    category: pick('category', '구분'),
    brewed_at: pickInt('brewed_at', 'BREWED AT'),
    roast_point: pickInt('roast_point', '로스팅 포인트'),
    availability: pick('availability', '운영상태'),
  }
}

export const coffeeRoutes = new Hono<{ Bindings: Env }>()

// ---------- 공개 조회 ----------

coffeeRoutes.get('/api/coffee', async (c) => {
  try {
    const { results } = await c.env.DB.prepare(`SELECT c.*, ${EFF_CUP_NOTES_SQL} FROM coffees c`).all<Row>()
    const cutoff = monthsAgoISO(3)
    const todayISO = kstTodayISO()
    const today: any[] = []
    const history: any[] = []
    for (const row of results) {
      const item = rowToApi(row)
      if (!item['커피']) continue
      const status = item['상태']
      if (status === '진행 중') { today.push(item); history.push(item) }
      else if (status === '예정') history.push(item)
      else if (status === '완료') {
        const ref = item['제공일']?.start || item['로스팅']?.start || ''
        if (ref && ref >= cutoff) history.push(item)
      }
    }
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

// ---------- 관리자 CRUD ----------

coffeeRoutes.get('/api/coffee/all', requirePin, async (c) => {
  const { results } = await c.env.DB
    .prepare(
      `SELECT c.*, ${EFF_CUP_NOTES_SQL} FROM coffees c ` +
        "ORDER BY CASE WHEN c.status='예정' THEN 0 ELSE 1 END, c.roast_date DESC, c.id DESC",
    )
    .all<Row>()
  return c.json({ success: true, items: results.map(rowToApi) })
})

coffeeRoutes.get('/api/coffee/:id{[0-9]+}', requirePin, async (c) => {
  const item = await getById(c.env.DB, parseInt(c.req.param('id'), 10))
  if (!item) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true, item })
})

coffeeRoutes.post('/api/coffee', requirePin, async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  const parsed = parsePayload(data)
  if (!parsed.name) return c.json({ success: false, error: '원두 이름(name)은 필수' }, 400)
  if (parsed.status === '진행 중' && !parsed.serve_date) parsed.serve_date = kstTodayISO()
  const newId = await createCoffee(c.env.DB, parsed)
  if ('cup_notes' in parsed) await syncBeanCupNotes(c.env.DB, newId, parsed.cup_notes)
  if (parsed.status === '진행 중') await completeOtherInProgress(c.env.DB, newId)
  return c.json({ success: true, id: newId, item: await getById(c.env.DB, newId) })
})

coffeeRoutes.put('/api/coffee/:id{[0-9]+}', requirePin, async (c) => {
  const coffeeId = parseInt(c.req.param('id'), 10)
  const data = (await c.req.json().catch(() => ({}))) as Row
  const rawParsed = parsePayload(data)
  const parsed: Row = {}
  for (const [k, v] of Object.entries(rawParsed)) if (v !== null || k in data) parsed[k] = v
  if (parsed.status === '진행 중' && !parsed.serve_date) parsed.serve_date = kstTodayISO()
  if (!(await updateCoffee(c.env.DB, coffeeId, parsed)))
    return c.json({ success: false, error: 'not found or no changes' }, 404)
  if ('cup_notes' in parsed) await syncBeanCupNotes(c.env.DB, coffeeId, parsed.cup_notes)
  if (parsed.status === '진행 중') await completeOtherInProgress(c.env.DB, coffeeId)
  let cascaded = 0
  if (parsed.availability) {
    const item = await getById(c.env.DB, coffeeId)
    if (item && item['커피']) {
      const res = await c.env.DB
        .prepare(
          "UPDATE coffees SET availability=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE name=?",
        )
        .bind(parsed.availability, item['커피'])
        .run()
      cascaded = (res.meta.changes as number) ?? 0
    }
  }
  return c.json({ success: true, item: await getById(c.env.DB, coffeeId), cascaded })
})

coffeeRoutes.delete('/api/coffee/:id{[0-9]+}', requirePin, async (c) => {
  const res = await c.env.DB.prepare('DELETE FROM coffees WHERE id=?').bind(parseInt(c.req.param('id'), 10)).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

// GET /api/suggestions (db.py suggestions)
coffeeRoutes.get('/api/suggestions', requirePin, async (c) => {
  const db = c.env.DB
  const distinct = async (col: string, limit = 50): Promise<string[]> => {
    const { results } = await db
      .prepare(
        `SELECT ${col} AS v, MAX(id) AS last_id FROM coffees ` +
          `WHERE ${col} IS NOT NULL AND ${col} != '' GROUP BY ${col} ORDER BY last_id DESC LIMIT ?`,
      )
      .bind(limit)
      .all<Row>()
    return results.map((r) => r.v)
  }
  const rawNotes = await distinct('cup_notes', 200)
  const seen = new Set<string>()
  const individualNotes: string[] = []
  for (const entry of rawNotes)
    for (let note of entry.split(',')) {
      note = note.trim()
      if (note && !seen.has(note)) { seen.add(note); individualNotes.push(note) }
    }
  const lastRow = await db
    .prepare("SELECT cup_notes FROM coffees WHERE cup_notes IS NOT NULL AND cup_notes != '' ORDER BY id DESC LIMIT 1")
    .first<Row>()
  return c.json({
    success: true,
    name: await distinct('name'),
    roastery: await distinct('roastery'),
    process: await distinct('process'),
    cup_notes: individualNotes,
    last_cup_notes: lastRow?.cup_notes || '',
  })
})

// ---------- 피드백 (app.py 431~607) ----------

const FEEDBACK_RATE_WINDOW_SEC = 3600
const FEEDBACK_RATE_MAX = 5
const FEEDBACK_MAX_CUP_NOTES = 3
const FEEDBACK_NICKNAME_MAX = 20
const FEEDBACK_COMMENT_MAX = 500
const FEEDBACK_NOTE_MAX = 30
const FEEDBACK_NOTE_OPTIONS_MAX = 10
const NOTE_SPLIT_RE = /[,/\n;|]/

function cleanNotes(value: any): string[] {
  if (!Array.isArray(value)) return []
  const out: string[] = []
  const seen = new Set<string>()
  for (const item of value) {
    if (typeof item !== 'string') continue
    const s = item.trim().slice(0, FEEDBACK_NOTE_MAX)
    if (!s || seen.has(s)) continue
    seen.add(s)
    out.push(s)
    if (out.length >= FEEDBACK_MAX_CUP_NOTES) break
  }
  return out
}

function feedbackRowToDict(row: Row) {
  let notes: any[] = []
  if (row.cup_notes_json) {
    try {
      const p = JSON.parse(row.cup_notes_json)
      if (Array.isArray(p)) notes = p
    } catch { /* ignore */ }
  }
  return {
    id: row.id,
    coffee_id: row.coffee_id,
    coffee_name: row.coffee_name ?? null,
    nickname: row.nickname || '',
    rating: row.rating,
    cup_notes: notes,
    comment: row.comment || '',
    created_at: row.created_at,
  }
}

coffeeRoutes.post('/api/feedback', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  const coffeeId = parseInt(data.coffee_id, 10)
  const rating = parseInt(data.rating, 10)
  if (!Number.isFinite(coffeeId) || !Number.isFinite(rating))
    return c.json({ success: false, error: 'coffee_id와 rating(정수) 필수' }, 400)
  if (rating < 1 || rating > 5) return c.json({ success: false, error: 'rating은 1~5' }, 400)
  const item = await getById(c.env.DB, coffeeId)
  if (!item) return c.json({ success: false, error: 'coffee not found' }, 404)
  const status = item['상태']
  const serveStart = item['제공일']?.start ?? null
  const allowed = status === '진행 중' || (status === '완료' && serveStart === kstTodayISO())
  if (!allowed)
    return c.json(
      { success: false, error: 'not_serving', message: '오늘 제공된 커피에만 피드백을 남길 수 있어요' },
      403,
    )
  const nickname = String(data.nickname || '').trim().slice(0, FEEDBACK_NICKNAME_MAX)
  const comment = String(data.comment || '').trim().slice(0, FEEDBACK_COMMENT_MAX)
  const notes = cleanNotes(data.cup_notes)
  const ipHash = await sha256Hex(clientIp(c.req.raw) + '|' + c.env.SESSION_SECRET)
  const cutoff = new Date(Date.now() - FEEDBACK_RATE_WINDOW_SEC * 1000).toISOString().slice(0, 19) + 'Z'
  const cnt = await c.env.DB
    .prepare('SELECT COUNT(*) AS c FROM feedback WHERE ip_hash=? AND created_at > ?')
    .bind(ipHash, cutoff)
    .first<Row>()
  if ((cnt?.c ?? 0) >= FEEDBACK_RATE_MAX)
    return c.json({ success: false, error: 'rate_limited', retry_after: FEEDBACK_RATE_WINDOW_SEC }, 429)
  const res = await c.env.DB
    .prepare(
      'INSERT INTO feedback (coffee_id, coffee_name, nickname, rating, cup_notes_json, comment, ip_hash) ' +
        'VALUES (?,?,?,?,?,?,?)',
    )
    .bind(
      coffeeId, item['커피'] || null, nickname || null, rating,
      notes.length ? JSON.stringify(notes) : null, comment || null, ipHash,
    )
    .run()
  return c.json({ success: true, id: res.meta.last_row_id })
})

coffeeRoutes.get('/api/feedback', requirePin, async (c) => {
  const cidRaw = c.req.query('coffee_id') || ''
  const cid = cidRaw ? parseInt(cidRaw, 10) : NaN
  let results: Row[]
  if (Number.isFinite(cid)) {
    const nameRow = await c.env.DB.prepare('SELECT name FROM coffees WHERE id=?').bind(cid).first<Row>()
    if (nameRow?.name) {
      results = (
        await c.env.DB
          .prepare(
            'SELECT id, coffee_id, coffee_name, nickname, rating, cup_notes_json, comment, created_at ' +
              'FROM feedback WHERE coffee_name = ? OR coffee_id = ? ORDER BY created_at DESC LIMIT 500',
          )
          .bind(nameRow.name, cid)
          .all<Row>()
      ).results
    } else {
      results = (
        await c.env.DB
          .prepare(
            'SELECT id, coffee_id, coffee_name, nickname, rating, cup_notes_json, comment, created_at ' +
              'FROM feedback WHERE coffee_id=? ORDER BY created_at DESC LIMIT 500',
          )
          .bind(cid)
          .all<Row>()
      ).results
    }
  } else {
    results = (
      await c.env.DB
        .prepare(
          'SELECT f.id, f.coffee_id, f.nickname, f.rating, f.cup_notes_json, f.comment, f.created_at, ' +
            'COALESCE(f.coffee_name, c.name) AS coffee_name FROM feedback f ' +
            'LEFT JOIN coffees c ON c.id = f.coffee_id ORDER BY f.created_at DESC LIMIT 500',
        )
        .all<Row>()
    ).results
  }
  return c.json({ success: true, items: results.map(feedbackRowToDict) })
})

coffeeRoutes.delete('/api/feedback/:id{[0-9]+}', requirePin, async (c) => {
  const res = await c.env.DB.prepare('DELETE FROM feedback WHERE id=?').bind(parseInt(c.req.param('id'), 10)).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

coffeeRoutes.put('/api/feedback/:id{[0-9]+}', requirePin, async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  let rating: number | null = null
  if (data.rating !== undefined && data.rating !== null) {
    rating = parseInt(data.rating, 10)
    if (!Number.isFinite(rating)) return c.json({ success: false, error: 'rating은 정수' }, 400)
    if (rating < 1 || rating > 5) return c.json({ success: false, error: 'rating은 1~5' }, 400)
  }
  const sets: string[] = []
  const vals: any[] = []
  if (rating !== null) { sets.push('rating=?'); vals.push(rating) }
  if (data.comment !== undefined && data.comment !== null) {
    sets.push('comment=?')
    vals.push(String(data.comment).trim().slice(0, FEEDBACK_COMMENT_MAX) || null)
  }
  if (data.nickname !== undefined && data.nickname !== null) {
    sets.push('nickname=?')
    vals.push(String(data.nickname).trim().slice(0, FEEDBACK_NICKNAME_MAX) || null)
  }
  if (!sets.length) return c.json({ success: false, error: 'not found or no changes' }, 404)
  vals.push(parseInt(c.req.param('id'), 10))
  const res = await c.env.DB.prepare(`UPDATE feedback SET ${sets.join(',')} WHERE id=?`).bind(...vals).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found or no changes' }, 404)
  return c.json({ success: true })
})

// 공개 — 평균 별점/건수 (db.py feedback_summary_for_coffee)
coffeeRoutes.get('/api/feedback/summary/:id{[0-9]+}', async (c) => {
  const coffeeId = parseInt(c.req.param('id'), 10)
  const db = c.env.DB
  const nameRow = await db.prepare('SELECT name FROM coffees WHERE id=?').bind(coffeeId).first<Row>()
  const whereSql = nameRow?.name ? 'WHERE (coffee_name = ? OR coffee_id = ?)' : 'WHERE coffee_id = ?'
  const whereArgs = nameRow?.name ? [nameRow.name, coffeeId] : [coffeeId]
  const agg = await db
    .prepare(`SELECT COUNT(*) AS c, AVG(rating) AS avg_rating FROM feedback ${whereSql}`)
    .bind(...whereArgs)
    .first<Row>()
  const { results } = await db
    .prepare(`SELECT cup_notes_json FROM feedback ${whereSql} AND cup_notes_json IS NOT NULL`)
    .bind(...whereArgs)
    .all<Row>()
  const tallies: Record<string, number> = {}
  for (const r of results) {
    try {
      const arr = JSON.parse(r.cup_notes_json)
      if (Array.isArray(arr))
        for (const note of arr)
          if (typeof note === 'string' && note.trim()) tallies[note.trim()] = (tallies[note.trim()] || 0) + 1
    } catch { /* ignore */ }
  }
  const topNotes = Object.entries(tallies)
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .slice(0, 5)
  return c.json({
    success: true,
    count: agg?.c ?? 0,
    avg_rating: Math.round(((agg?.avg_rating as number) || 0) * 100) / 100,
    top_notes: topNotes.map(([note, count]) => ({ note, count })),
  })
})

// 공개 — 컵노트 토큰 후보 (app.py api_feedback_note_options + db.py popular_cup_notes)
coffeeRoutes.get('/api/feedback/note-options', async (c) => {
  const cidRaw = c.req.query('coffee_id') || ''
  const current: string[] = []
  if (cidRaw) {
    const cid = parseInt(cidRaw, 10)
    const item = Number.isFinite(cid) ? await getById(c.env.DB, cid) : null
    if (item && item['컵노트']) {
      const seen = new Set<string>()
      for (let note of String(item['컵노트']).split(NOTE_SPLIT_RE)) {
        note = note.trim()
        if (note && !seen.has(note)) { seen.add(note); current.push(note) }
      }
    }
  }
  // popular_cup_notes
  const { results } = await c.env.DB
    .prepare("SELECT cup_notes FROM coffees WHERE cup_notes IS NOT NULL AND cup_notes != ''")
    .all<Row>()
  const counter: Record<string, number> = {}
  for (const r of results)
    for (let note of String(r.cup_notes || '').split(NOTE_SPLIT_RE)) {
      note = note.trim()
      if (note) counter[note] = (counter[note] || 0) + 1
    }
  const popular = Object.entries(counter)
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .slice(0, FEEDBACK_NOTE_OPTIONS_MAX * 2)
    .map(([n]) => n)
  const seen = new Set(current)
  const merged = [...current]
  for (const n of popular) {
    if (!seen.has(n)) {
      seen.add(n)
      merged.push(n)
      if (merged.length >= FEEDBACK_NOTE_OPTIONS_MAX) break
    }
  }
  return c.json({
    success: true,
    notes: merged.slice(0, FEEDBACK_NOTE_OPTIONS_MAX),
    current_count: current.length,
  })
})

// 카드 PNG — 마이그레이션 결정: 보류 (docs/CLOUDFLARE-MIGRATION.md)
coffeeRoutes.post('/api/coffee/:id{[0-9]+}/card-token', requirePin, (c) =>
  c.json({ success: false, error: 'card download not available (migration)' }, 501))
coffeeRoutes.get('/api/coffee/:id{[0-9]+}/card.png', (c) =>
  c.json({ success: false, error: 'card download not available (migration)' }, 501))
