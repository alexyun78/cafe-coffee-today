// Q 그레이더 훈련 관리 API — 커리큘럼(읽기) + 훈련 일지/루틴/설정(쓰기).
// 스키마: scripts/qgrader_schema.sql · 커리큘럼 seed: scripts/qgrader_sync.py
// 모든 라우트 PIN 필요 (관리자 전용). 응답 형태는 다른 API와 동일하게 {success,...}.
import { Hono } from 'hono'
import { Env, Row, kstTodayISO, utcNowISO } from './util'
import { requirePin } from './auth'

export const qgraderRoutes = new Hono<{ Bindings: Env }>()

qgraderRoutes.use('/api/qgrader/*', requirePin)

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/** 숫자 필드 정규화 — 빈 값/미입력은 null, 범위 밖은 클램프 */
function num(v: any, min: number, max: number, int = true): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  const c = Math.min(max, Math.max(min, n))
  return int ? Math.round(c) : Math.round(c * 10) / 10
}

/** 주 시작(월요일) — 'YYYY-MM-DD' */
export function weekStart(dateISO: string): string {
  const d = new Date(dateISO + 'T00:00:00Z')
  const dow = (d.getUTCDay() + 6) % 7 // 월=0
  d.setUTCDate(d.getUTCDate() - dow)
  return d.toISOString().slice(0, 10)
}

// ---------- 커리큘럼 (md 에서 seed 된 읽기 전용 자료) ----------

qgraderRoutes.get('/api/qgrader/curriculum', async (c) => {
  const db = c.env.DB
  const [curr, roadmap, targets, routine, ref] = await db.batch([
    db.prepare('SELECT version, source, title, created_at FROM qg_curriculum ORDER BY id DESC LIMIT 1'),
    db.prepare('SELECT * FROM qg_roadmap ORDER BY sort_order'),
    db.prepare('SELECT metric, month, value, note FROM qg_targets ORDER BY metric, month'),
    db.prepare('SELECT id, label, cadence, detail, sort_order FROM qg_routine_items WHERE active=1 ORDER BY sort_order'),
    db.prepare('SELECT section, sort_order, data FROM qg_reference ORDER BY section, sort_order'),
  ])
  const reference: Record<string, Row[]> = {}
  for (const r of ref.results as any[]) {
    ;(reference[r.section] ||= []).push(JSON.parse(r.data))
  }
  const byMetric: Record<string, Row[]> = {}
  for (const t of targets.results as any[]) (byMetric[t.metric] ||= []).push({ month: t.month, value: t.value, note: t.note })
  return c.json({
    success: true,
    meta: (curr.results[0] as any) || null,
    roadmap: roadmap.results,
    targets: byMetric,
    routine_items: routine.results,
    reference,
  })
})

/** 학습플랜 원문 마크다운 */
qgraderRoutes.get('/api/qgrader/curriculum/markdown', async (c) => {
  const row = await c.env.DB.prepare(
    'SELECT version, title, body_md, created_at FROM qg_curriculum ORDER BY id DESC LIMIT 1',
  ).first<any>()
  if (!row) return c.json({ success: false, error: 'no curriculum' }, 404)
  return c.json({ success: true, ...row })
})

// ---------- 훈련 일지 ----------

qgraderRoutes.get('/api/qgrader/logs', async (c) => {
  const from = c.req.query('from') || ''
  const to = c.req.query('to') || ''
  const limit = Math.min(2000, Math.max(1, Number(c.req.query('limit') || 800)))
  const where: string[] = []
  const args: any[] = []
  if (DATE_RE.test(from)) { where.push('date >= ?'); args.push(from) }
  if (DATE_RE.test(to)) { where.push('date <= ?'); args.push(to) }
  const sql =
    'SELECT date, aroma, acid, tri, cup, defect, written, minutes, note, updated_at FROM qg_logs' +
    (where.length ? ' WHERE ' + where.join(' AND ') : '') +
    ' ORDER BY date ASC LIMIT ?'
  const rs = await c.env.DB.prepare(sql).bind(...args, limit).all()
  return c.json({ success: true, items: rs.results, count: rs.results.length })
})

/** 하루 1행 UPSERT — 같은 날짜를 다시 저장하면 보낸 필드만 갱신 */
qgraderRoutes.post('/api/qgrader/logs', async (c) => {
  const b = (await c.req.json().catch(() => ({}))) as any
  const date = String(b.date || '').trim() || kstTodayISO()
  if (!DATE_RE.test(date)) return c.json({ success: false, error: 'invalid date' }, 400)
  const now = utcNowISO()
  const v = {
    aroma: num(b.aroma, 0, 36),
    acid: num(b.acid, 0, 100, false),
    tri: num(b.tri, 0, 6),
    cup: num(b.cup, 0, 20),
    defect: num(b.defect, 0, 100, false),
    written: num(b.written, 0, 100, false),
    minutes: num(b.minutes, 0, 1440),
    note: b.note === undefined || b.note === null ? null : String(b.note).slice(0, 2000),
  }
  await c.env.DB.prepare(
    `INSERT INTO qg_logs (date,aroma,acid,tri,cup,defect,written,minutes,note,created_at,updated_at)
     VALUES (?,?,?,?,?,?,?,?,?,?,?)
     ON CONFLICT(date) DO UPDATE SET
       aroma=COALESCE(excluded.aroma, qg_logs.aroma),
       acid=COALESCE(excluded.acid, qg_logs.acid),
       tri=COALESCE(excluded.tri, qg_logs.tri),
       cup=COALESCE(excluded.cup, qg_logs.cup),
       defect=COALESCE(excluded.defect, qg_logs.defect),
       written=COALESCE(excluded.written, qg_logs.written),
       minutes=COALESCE(excluded.minutes, qg_logs.minutes),
       note=COALESCE(excluded.note, qg_logs.note),
       updated_at=excluded.updated_at`,
  )
    .bind(date, v.aroma, v.acid, v.tri, v.cup, v.defect, v.written, v.minutes, v.note, now, now)
    .run()
  const row = await c.env.DB.prepare('SELECT * FROM qg_logs WHERE date=?').bind(date).first()
  return c.json({ success: true, item: row })
})

/** 필드 비우기까지 반영하는 전체 교체 */
qgraderRoutes.put('/api/qgrader/logs/:date', async (c) => {
  const date = c.req.param('date')
  if (!DATE_RE.test(date)) return c.json({ success: false, error: 'invalid date' }, 400)
  const b = (await c.req.json().catch(() => ({}))) as any
  const now = utcNowISO()
  await c.env.DB.prepare(
    `INSERT INTO qg_logs (date,aroma,acid,tri,cup,defect,written,minutes,note,created_at,updated_at)
     VALUES (?,?,?,?,?,?,?,?,?,?,?)
     ON CONFLICT(date) DO UPDATE SET
       aroma=excluded.aroma, acid=excluded.acid, tri=excluded.tri, cup=excluded.cup,
       defect=excluded.defect, written=excluded.written, minutes=excluded.minutes,
       note=excluded.note, updated_at=excluded.updated_at`,
  )
    .bind(
      date, num(b.aroma, 0, 36), num(b.acid, 0, 100, false), num(b.tri, 0, 6), num(b.cup, 0, 20),
      num(b.defect, 0, 100, false), num(b.written, 0, 100, false), num(b.minutes, 0, 1440),
      b.note ? String(b.note).slice(0, 2000) : null, now, now,
    )
    .run()
  const row = await c.env.DB.prepare('SELECT * FROM qg_logs WHERE date=?').bind(date).first()
  return c.json({ success: true, item: row })
})

qgraderRoutes.delete('/api/qgrader/logs/:date', async (c) => {
  const date = c.req.param('date')
  if (!DATE_RE.test(date)) return c.json({ success: false, error: 'invalid date' }, 400)
  const r = await c.env.DB.prepare('DELETE FROM qg_logs WHERE date=?').bind(date).run()
  return c.json({ success: true, deleted: r.meta.changes || 0 })
})

// ---------- 주간 루틴 체크 ----------

qgraderRoutes.get('/api/qgrader/routine', async (c) => {
  const q = c.req.query('week') || ''
  const week = DATE_RE.test(q) ? weekStart(q) : weekStart(kstTodayISO())
  const rs = await c.env.DB.prepare(
    `SELECT i.id, i.label, i.cadence, i.detail, i.sort_order,
            COALESCE(ch.done, 0) AS done
       FROM qg_routine_items i
       LEFT JOIN qg_routine_checks ch ON ch.item_id = i.id AND ch.week = ?
      WHERE i.active = 1
      ORDER BY i.sort_order`,
  ).bind(week).all()
  return c.json({ success: true, week, items: rs.results })
})

qgraderRoutes.post('/api/qgrader/routine', async (c) => {
  const b = (await c.req.json().catch(() => ({}))) as any
  const week = DATE_RE.test(String(b.week || '')) ? weekStart(String(b.week)) : weekStart(kstTodayISO())
  const itemId = Number(b.item_id)
  if (!Number.isInteger(itemId)) return c.json({ success: false, error: 'invalid item_id' }, 400)
  const done = b.done ? 1 : 0
  await c.env.DB.prepare(
    `INSERT INTO qg_routine_checks (week,item_id,done,updated_at) VALUES (?,?,?,?)
     ON CONFLICT(week,item_id) DO UPDATE SET done=excluded.done, updated_at=excluded.updated_at`,
  ).bind(week, itemId, done, utcNowISO()).run()
  return c.json({ success: true, week, item_id: itemId, done })
})

// ---------- 설정 ----------

qgraderRoutes.get('/api/qgrader/settings', async (c) => {
  const rs = await c.env.DB.prepare('SELECT key, value FROM qg_settings').all()
  const out: Row = {}
  for (const r of rs.results as any[]) out[r.key] = r.value
  return c.json({ success: true, settings: out })
})

const SETTING_KEYS = new Set(['exam_date', 'memo'])

qgraderRoutes.put('/api/qgrader/settings', async (c) => {
  const b = (await c.req.json().catch(() => ({}))) as any
  const now = utcNowISO()
  const stmts = []
  for (const [k, val] of Object.entries(b || {})) {
    if (!SETTING_KEYS.has(k)) continue
    stmts.push(
      c.env.DB.prepare(
        `INSERT INTO qg_settings (key,value,updated_at) VALUES (?,?,?)
         ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at`,
      ).bind(k, val === null ? null : String(val).slice(0, 500), now),
    )
  }
  if (stmts.length) await c.env.DB.batch(stmts)
  return c.json({ success: true, saved: stmts.length })
})

// ---------- 요약 (대시보드 타일) ----------

qgraderRoutes.get('/api/qgrader/summary', async (c) => {
  const db = c.env.DB
  const today = kstTodayISO()
  const month = today.slice(0, 7)
  const [logs, exam, targets, routine] = await db.batch([
    db.prepare('SELECT date, aroma, acid, tri, cup, minutes FROM qg_logs ORDER BY date DESC LIMIT 400'),
    db.prepare("SELECT value FROM qg_settings WHERE key='exam_date'"),
    db.prepare('SELECT metric, value FROM qg_targets WHERE month=?').bind(month),
    db.prepare(
      `SELECT COUNT(*) AS done FROM qg_routine_checks ch
         JOIN qg_routine_items i ON i.id=ch.item_id AND i.active=1 AND i.cadence='weekly'
        WHERE ch.week=? AND ch.done=1`,
    ).bind(weekStart(today)),
  ])
  const rows = logs.results as any[]

  // 연속 기록일 — 오늘(없으면 어제)부터 거꾸로
  const dates = new Set(rows.map((r) => r.date))
  let streak = 0
  const cur = new Date(today + 'T00:00:00Z')
  if (!dates.has(today)) cur.setUTCDate(cur.getUTCDate() - 1)
  while (dates.has(cur.toISOString().slice(0, 10))) {
    streak++
    cur.setUTCDate(cur.getUTCDate() - 1)
  }

  const latestOf = (k: string) => {
    for (const r of rows) if (r[k] !== null && r[k] !== undefined) return { value: r[k], date: r.date }
    return null
  }
  const tmap: Record<string, number> = {}
  for (const t of targets.results as any[]) tmap[t.metric] = t.value
  const weeklyTotal = await db
    .prepare("SELECT COUNT(*) AS c FROM qg_routine_items WHERE active=1 AND cadence='weekly'")
    .first<any>()

  return c.json({
    success: true,
    today,
    month,
    exam_date: (exam.results[0] as any)?.value || null,
    total_logs: rows.length,
    streak,
    latest: { aroma: latestOf('aroma'), acid: latestOf('acid'), tri: latestOf('tri') },
    month_targets: tmap,
    routine_week: {
      week: weekStart(today),
      done: (routine.results[0] as any)?.done ?? 0,
      total: weeklyTotal?.c ?? 0,
    },
  })
})
