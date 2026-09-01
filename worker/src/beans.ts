// 생두 관리 — app.py 658~1012 + db.py suppliers/green_beans/purchases/roasting_logs/
// inventory/pricing 포팅. 재고 = computed query (구매 - 로스팅 + 보정) 동일 유지.
import { Hono } from 'hono'
import { Env, Row, kstTodayISO, utcNowISO, monthsAgoISO } from './util'
import { requirePin } from './auth'
import { createCoffee, findActiveByName } from './coffee'

export const beanRoutes = new Hono<{ Bindings: Env }>()
// 관리자 전용 가드 — 이 라우터의 경로에만 정확히 적용
// (use('/api/*') 블랭킷은 이후 등록되는 공개 API까지 가로채므로 금지)
for (const p of [
  '/api/suppliers', '/api/suppliers/*',
  '/api/green-beans', '/api/green-beans/*',
  '/api/purchases', '/api/purchases/*',
  '/api/roasting-logs', '/api/roasting-logs/*',
  '/api/inventory',
  '/api/pricing', '/api/pricing/*',
]) beanRoutes.use(p, requirePin)

// ---------- 원두 종류 (싱글 / 블랜드 / 디카페인) ----------

/** 생두의 원두 종류. 알 수 없는 값은 '싱글'로 정규화한다. */
export const BEAN_TYPES = ['싱글', '블랜드', '디카페인'] as const

export function normBeanType(v: any): string {
  const s = String(v ?? '').trim()
  if (s === '블렌드') return '블랜드'   // 표기 흔들림 흡수
  return (BEAN_TYPES as readonly string[]).includes(s) ? s : '싱글'
}

/** 원두 종류의 창구는 생두 마스터(green_beans.bean_type) 하나뿐이다.
 *  어디서 바꾸든(생두 폼·구매 폼·로스팅 폼) 그 생두의 모든 로스팅 기록을 같은 값으로 통일한다.
 *  블랜드가 되면 오늘의 커피 연동도 전부 끈다(블랜드는 등록 불가). */
async function syncRoastUsageToBean(db: D1Database, gbId: number): Promise<string> {
  const bean = await db.prepare('SELECT bean_type FROM green_beans WHERE id=?').bind(gbId).first<Row>()
  const t = normBeanType(bean?.bean_type)
  if (!bean) return t
  await db.prepare('UPDATE roasting_logs SET usage_type=? WHERE green_bean_id=?').bind(t, gbId).run()
  if (t === '블랜드')
    await db.prepare('UPDATE roasting_logs SET make_coffee=0 WHERE green_bean_id=?').bind(gbId).run()
  return t
}

/** 로스팅 폼 등에서 온 사용 타입을 생두 마스터에 반영하고 전체를 통일한다. */
async function setBeanTypeFrom(db: D1Database, gbId: number, type: any): Promise<string> {
  const t = normBeanType(type)
  await db
    .prepare(
      "UPDATE green_beans SET bean_type=?, is_decaf=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') " +
        'WHERE id=? AND bean_type<>?',
    )
    .bind(t, t === '디카페인' ? 1 : 0, gbId, t)
    .run()
  return await syncRoastUsageToBean(db, gbId)
}

/** 요청 본문에서 bean_type / is_decaf 를 읽어 둘을 일관되게 맞춘 값을 돌려준다.
 *  is_decaf 는 레거시 Flask·기존 응답 호환을 위해 계속 동기화한다. */
function beanTypeFields(data: Row): { bean_type: string; is_decaf: number } | null {
  if ('bean_type' in data) {
    const t = normBeanType(data.bean_type)
    return { bean_type: t, is_decaf: t === '디카페인' ? 1 : 0 }
  }
  if ('is_decaf' in data) {
    const d = data.is_decaf ? 1 : 0
    return { bean_type: d ? '디카페인' : '싱글', is_decaf: d }
  }
  return null
}

// ---------- 공용 쿼리 조각 ----------

const GB_LIST_SQL = (where: string) => `
    SELECT gb.*, s.name AS supplier_name, s.short_name AS supplier_short,
        COALESCE(p_sum.purchased_kg, 0) AS purchased_kg,
        COALESCE(r_sum.used_kg, 0) AS used_kg,
        COALESCE(p_sum.purchased_kg, 0) - COALESCE(r_sum.used_kg, 0)
            + COALESCE(gb.stock_adjustment_kg, 0) AS remaining_kg,
        COALESCE(p_sum.avg_unit_price, 0) AS avg_unit_price,
        COALESCE(p_last.last_unit_price, 0) AS last_unit_price,
        COALESCE(p_last.last_discounted_unit_price, 0) AS last_discounted_unit_price,
        COALESCE(r_sum.roast_count, 0) AS roast_count,
        r_sum.last_roast_date AS last_roast_date
    FROM green_beans gb
    LEFT JOIN suppliers s ON s.id = gb.supplier_id
    LEFT JOIN (
        SELECT green_bean_id, SUM(quantity_kg) AS purchased_kg,
               ROUND(CAST(SUM(total_price) AS REAL) / NULLIF(SUM(quantity_kg), 0)) AS avg_unit_price
        FROM purchases GROUP BY green_bean_id
    ) p_sum ON p_sum.green_bean_id = gb.id
    LEFT JOIN (
        SELECT green_bean_id, unit_price AS last_unit_price,
               ROUND(CAST(total_price AS REAL) / NULLIF(quantity_kg, 0)) AS last_discounted_unit_price
        FROM (
            SELECT green_bean_id, unit_price, total_price, quantity_kg,
                   ROW_NUMBER() OVER (PARTITION BY green_bean_id
                                      ORDER BY purchase_date DESC, id DESC) AS rn
            FROM purchases
        ) WHERE rn = 1
    ) p_last ON p_last.green_bean_id = gb.id
    LEFT JOIN (
        SELECT green_bean_id, SUM(input_weight_g) / 1000.0 AS used_kg,
               COUNT(*) AS roast_count, MAX(roast_date) AS last_roast_date
        FROM roasting_logs GROUP BY green_bean_id
    ) r_sum ON r_sum.green_bean_id = gb.id
    ${where}
    ORDER BY remaining_kg DESC, gb.name
`

const GB_GET_SQL = `
    SELECT gb.*, s.name AS supplier_name, s.short_name AS supplier_short,
        COALESCE(p_sum.purchased_kg, 0) AS purchased_kg,
        COALESCE(r_sum.used_kg, 0) AS used_kg,
        COALESCE(p_sum.purchased_kg, 0) - COALESCE(r_sum.used_kg, 0)
            + COALESCE(gb.stock_adjustment_kg, 0) AS remaining_kg,
        COALESCE(p_sum.avg_unit_price, 0) AS avg_unit_price,
        COALESCE(p_last.last_unit_price, 0) AS last_unit_price,
        COALESCE(p_last.last_discounted_unit_price, 0) AS last_discounted_unit_price,
        COALESCE(r_sum.avg_loss_pct, 0) AS avg_loss_pct
    FROM green_beans gb
    LEFT JOIN suppliers s ON s.id = gb.supplier_id
    LEFT JOIN (
        SELECT green_bean_id, SUM(quantity_kg) AS purchased_kg,
               ROUND(CAST(SUM(total_price) AS REAL) / NULLIF(SUM(quantity_kg), 0)) AS avg_unit_price
        FROM purchases GROUP BY green_bean_id
    ) p_sum ON p_sum.green_bean_id = gb.id
    LEFT JOIN (
        SELECT green_bean_id, unit_price AS last_unit_price,
               ROUND(CAST(total_price AS REAL) / NULLIF(quantity_kg, 0)) AS last_discounted_unit_price
        FROM (
            SELECT green_bean_id, unit_price, total_price, quantity_kg,
                   ROW_NUMBER() OVER (PARTITION BY green_bean_id
                                      ORDER BY purchase_date DESC, id DESC) AS rn
            FROM purchases
        ) WHERE rn = 1
    ) p_last ON p_last.green_bean_id = gb.id
    LEFT JOIN (
        SELECT green_bean_id, SUM(input_weight_g) / 1000.0 AS used_kg,
               AVG(moisture_loss_pct) AS avg_loss_pct
        FROM roasting_logs GROUP BY green_bean_id
    ) r_sum ON r_sum.green_bean_id = gb.id
    WHERE gb.id = ?
`

export async function getGreenBean(db: D1Database, gbId: number): Promise<Row | null> {
  return db.prepare(GB_GET_SQL).bind(gbId).first<Row>()
}

/** supplier_id 해석 — 없으면 supplier_name 으로 찾기/생성 (db.py _resolve_supplier_id) */
async function resolveSupplierId(db: D1Database, data: Row): Promise<number | null> {
  if (data.supplier_id) return parseInt(data.supplier_id, 10)
  const name = String(data.supplier_name || '').trim()
  if (!name) return null
  const row = await db
    .prepare('SELECT id FROM suppliers WHERE name = ? COLLATE NOCASE OR short_name = ? COLLATE NOCASE')
    .bind(name, name)
    .first<Row>()
  if (row) return row.id
  const res = await db.prepare('INSERT INTO suppliers (name, short_name) VALUES (?,?)').bind(name, name).run()
  return res.meta.last_row_id as number
}

/** 구매 폼 생두 찾기/생성 (db.py find_or_create_green_bean — 정체성 충돌 가드 포함) */
async function findOrCreateGreenBean(db: D1Database, data: Row): Promise<number> {
  const supplierId = await resolveSupplierId(db, data)
  const name = String(data.name || '').trim()
  const process = String(data.process || '').trim()
  let gid: number | null = data.green_bean_id ? parseInt(data.green_bean_id, 10) : null

  if (gid == null && name) {
    const row =
      supplierId == null
        ? await db
            .prepare('SELECT id FROM green_beans WHERE name=? AND process=? AND supplier_id IS NULL')
            .bind(name, process)
            .first<Row>()
        : await db
            .prepare('SELECT id FROM green_beans WHERE name=? AND process=? AND supplier_id=?')
            .bind(name, process, supplierId)
            .first<Row>()
    gid = row ? row.id : null
  }

  if (gid != null) {
    const curRow = await db.prepare('SELECT name, supplier_id, process FROM green_beans WHERE id=?').bind(gid).first<Row>()
    const targetName = name || curRow?.name || name
    const targetSupplier = supplierId !== null ? supplierId : curRow?.supplier_id ?? null
    const targetProcess = process || curRow?.process || process
    const identityChanged =
      !!curRow &&
      (targetName !== curRow.name || targetSupplier !== curRow.supplier_id || targetProcess !== curRow.process)
    let allowIdentity = true
    if (identityChanged) {
      const dup =
        targetSupplier == null
          ? await db
              .prepare('SELECT id FROM green_beans WHERE name=? AND process=? AND supplier_id IS NULL AND id<>?')
              .bind(targetName, targetProcess, gid)
              .first<Row>()
          : await db
              .prepare('SELECT id FROM green_beans WHERE name=? AND process=? AND supplier_id=? AND id<>?')
              .bind(targetName, targetProcess, targetSupplier, gid)
              .first<Row>()
      if (dup) allowIdentity = false
    }
    const sets: string[] = []
    const vals: any[] = []
    if (allowIdentity) {
      if (supplierId !== null) { sets.push('supplier_id=?'); vals.push(supplierId) }
      if (name) { sets.push('name=?'); vals.push(name) }
      if (process) { sets.push('process=?'); vals.push(process) }
    }
    for (const col of ['origin_country', 'grade', 'cup_notes']) {
      const v = data[col]
      if (v !== undefined && v !== null && String(v).trim() !== '') {
        sets.push(`${col}=?`)
        vals.push(String(v).trim())
      }
    }
    const bt = beanTypeFields(data)
    if (bt) {
      sets.push('bean_type=?'); vals.push(bt.bean_type)
      sets.push('is_decaf=?'); vals.push(bt.is_decaf)
    }
    if (sets.length) {
      sets.push("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
      vals.push(gid)
      await db.prepare(`UPDATE green_beans SET ${sets.join(',')} WHERE id=?`).bind(...vals).run()
    }
    if (bt) await syncRoastUsageToBean(db, gid)   // 종류가 바뀌면 이 생두의 모든 기록을 통일
    return gid
  }

  if (!process) throw new ValidationError('가공방식(process)은 필수입니다.')
  const newType = beanTypeFields(data) ?? { bean_type: '싱글', is_decaf: 0 }
  const res = await db
    .prepare(
      'INSERT INTO green_beans (name, supplier_id, origin_country, process, grade, cup_notes, bean_type, is_decaf, status) ' +
        'VALUES (?,?,?,?,?,?,?,?,?)',
    )
    .bind(
      name, supplierId, data.origin_country ?? null, process, data.grade ?? null,
      data.cup_notes ?? null, newType.bean_type, newType.is_decaf, '활성',
    )
    .run()
  return res.meta.last_row_id as number
}

class ValidationError extends Error {}

const isUniqueError = (e: any) => /UNIQUE constraint failed/i.test(String(e?.message || e))
const DUP_BEAN_MSG =
  '이미 같은 이름·공급처·가공방식의 생두가 있어요. 기존 생두를 선택해 재구매하거나 이름을 다르게 해 주세요.'

// ---------- Suppliers ----------

beanRoutes.get('/api/suppliers', async (c) => {
  const { results } = await c.env.DB.prepare('SELECT * FROM suppliers ORDER BY name').all<Row>()
  return c.json({ success: true, items: results })
})

beanRoutes.post('/api/suppliers', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  if (!data.name) return c.json({ success: false, error: 'name 필수' }, 400)
  const res = await c.env.DB
    .prepare('INSERT INTO suppliers (name, short_name, contact, notes) VALUES (?,?,?,?)')
    .bind(data.name, data.short_name ?? null, data.contact ?? null, data.notes ?? null)
    .run()
  return c.json({ success: true, id: res.meta.last_row_id })
})

beanRoutes.put('/api/suppliers/:id{[0-9]+}', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  const sets: string[] = []
  const vals: any[] = []
  for (const k of ['name', 'short_name', 'contact', 'notes', 'hidden'])
    if (k in data) { sets.push(`${k}=?`); vals.push(data[k]) }
  if (!sets.length) return c.json({ success: false, error: 'not found' }, 404)
  sets.push("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
  vals.push(parseInt(c.req.param('id'), 10))
  const res = await c.env.DB.prepare(`UPDATE suppliers SET ${sets.join(',')} WHERE id=?`).bind(...vals).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

beanRoutes.delete('/api/suppliers/:id{[0-9]+}', async (c) => {
  const res = await c.env.DB.prepare('DELETE FROM suppliers WHERE id=?').bind(parseInt(c.req.param('id'), 10)).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

// ---------- Green Beans ----------

beanRoutes.get('/api/green-beans', async (c) => {
  const includeInactive = c.req.query('all') === '1'
  const { results } = await c.env.DB.prepare(GB_LIST_SQL(includeInactive ? '' : "WHERE gb.status='활성'")).all<Row>()
  for (const r of results) r.display_name = r.name
  return c.json({ success: true, items: results })
})

// 주의: 라우트 등록 순서 — suggestions 가 :id 보다 먼저
beanRoutes.get('/api/green-beans/suggestions', async (c) => {
  const db = c.env.DB
  const [sup, proc, grade, orig, gb] = await db.batch([
    db.prepare('SELECT id, name, short_name FROM suppliers ORDER BY name'),
    db.prepare("SELECT DISTINCT process FROM green_beans WHERE process IS NOT NULL AND process != '' ORDER BY process"),
    db.prepare("SELECT DISTINCT grade FROM green_beans WHERE grade IS NOT NULL AND grade != '' ORDER BY grade"),
    db.prepare("SELECT DISTINCT origin_country FROM green_beans WHERE origin_country IS NOT NULL AND origin_country != '' ORDER BY origin_country"),
    db.prepare(
      "SELECT s.name AS supplier_name, gb.name AS bean_name FROM green_beans gb " +
        "JOIN suppliers s ON s.id = gb.supplier_id WHERE gb.name IS NOT NULL AND gb.name != '' " +
        'ORDER BY s.name, gb.name',
    ),
  ])
  const beansBySupplier: Record<string, string[]> = {}
  for (const r of gb.results as Row[]) {
    const lst = (beansBySupplier[r.supplier_name] ||= [])
    if (!lst.includes(r.bean_name)) lst.push(r.bean_name)
  }
  return c.json({
    success: true,
    suppliers: sup.results,
    processes: (proc.results as Row[]).map((r) => r.process),
    grades: (grade.results as Row[]).map((r) => r.grade),
    origins: (orig.results as Row[]).map((r) => r.origin_country),
    beans_by_supplier: beansBySupplier,
  })
})

beanRoutes.get('/api/green-beans/:id{[0-9]+}', async (c) => {
  const gbId = parseInt(c.req.param('id'), 10)
  const item = await getGreenBean(c.env.DB, gbId)
  if (!item) return c.json({ success: false, error: 'not found' }, 404)
  item.purchases = await listPurchases(c.env.DB, gbId, 50)
  item.roasting_logs = await listRoastingLogs(c.env.DB, gbId, 50)
  return c.json({ success: true, item })
})

beanRoutes.post('/api/green-beans', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  if (!data.name || !data.process) return c.json({ success: false, error: 'name, process 필수' }, 400)
  const supplierId = await resolveSupplierId(c.env.DB, data)
  const bt = beanTypeFields(data) ?? { bean_type: '싱글', is_decaf: 0 }
  try {
    const res = await c.env.DB
      .prepare(
        'INSERT INTO green_beans (name, supplier_id, origin_country, origin_region, process, grade, ' +
          'cup_notes, description, bean_type, is_decaf, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
      )
      .bind(
        data.name, supplierId, data.origin_country ?? null, data.origin_region ?? null,
        data.process, data.grade ?? null, data.cup_notes ?? null, data.description ?? null,
        bt.bean_type, bt.is_decaf, data.status ?? '활성',
      )
      .run()
    const newId = res.meta.last_row_id as number
    return c.json({ success: true, id: newId, item: await getGreenBean(c.env.DB, newId) })
  } catch (e) {
    if (isUniqueError(e)) return c.json({ success: false, error: DUP_BEAN_MSG }, 409)
    throw e
  }
})

beanRoutes.put('/api/green-beans/:id{[0-9]+}/stock', async (c) => {
  const gbId = parseInt(c.req.param('id'), 10)
  const data = (await c.req.json().catch(() => ({}))) as Row
  if (!('remaining_kg' in data) || data.remaining_kg === null || data.remaining_kg === '')
    return c.json({ success: false, error: 'remaining_kg 필수' }, 400)
  const target = parseFloat(data.remaining_kg)
  if (!Number.isFinite(target)) return c.json({ success: false, error: '잘못된 수량' }, 400)
  const row = await c.env.DB
    .prepare(
      `SELECT COALESCE((SELECT SUM(quantity_kg) FROM purchases WHERE green_bean_id=gb.id), 0) AS purchased_kg,
              COALESCE((SELECT SUM(input_weight_g)/1000.0 FROM roasting_logs WHERE green_bean_id=gb.id), 0) AS used_kg
       FROM green_beans gb WHERE gb.id=?`,
    )
    .bind(gbId)
    .first<Row>()
  if (!row) return c.json({ success: false, error: 'not found' }, 404)
  const adjustment = Math.round((target - (row.purchased_kg - row.used_kg)) * 1000) / 1000
  await c.env.DB
    .prepare("UPDATE green_beans SET stock_adjustment_kg=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?")
    .bind(adjustment, gbId)
    .run()
  return c.json({ success: true, item: await getGreenBean(c.env.DB, gbId) })
})

/** 품절 토글. status(활성/단종)와 별개다 — 품절은 목록에서 사라지지 않고
 *  재고 관리에 그대로 남되, 공개 원두 카드에서 뒤로 밀리고 인쇄에서 빠진다. */
beanRoutes.put('/api/green-beans/:id{[0-9]+}/sold-out', async (c) => {
  const gbId = parseInt(c.req.param('id'), 10)
  const data = (await c.req.json().catch(() => ({}))) as Row
  const soldOut = data.sold_out ? 1 : 0
  const res = await c.env.DB
    .prepare("UPDATE green_beans SET sold_out=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?")
    .bind(soldOut, gbId)
    .run()
  if (!res.meta.changes) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true, item: await getGreenBean(c.env.DB, gbId) })
})

beanRoutes.put('/api/green-beans/:id{[0-9]+}', async (c) => {
  const gbId = parseInt(c.req.param('id'), 10)
  let data = (await c.req.json().catch(() => ({}))) as Row
  if ('supplier_name' in data && !data.supplier_id)
    data = { ...data, supplier_id: await resolveSupplierId(c.env.DB, data) }
  const allowed = ['name', 'supplier_id', 'origin_country', 'origin_region', 'process', 'grade',
    'cup_notes', 'description', 'status', 'hidden', 'sold_out']
  const sets: string[] = []
  const vals: any[] = []
  for (const k of allowed) if (k in data) { sets.push(`${k}=?`); vals.push(data[k]) }
  // bean_type 과 is_decaf 는 항상 함께 맞춘다 (둘 중 무엇이 와도)
  const bt = beanTypeFields(data)
  if (bt) {
    sets.push('bean_type=?'); vals.push(bt.bean_type)
    sets.push('is_decaf=?'); vals.push(bt.is_decaf)
  }
  if (!sets.length) return c.json({ success: false, error: 'not found' }, 404)
  sets.push("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
  vals.push(gbId)
  try {
    const res = await c.env.DB.prepare(`UPDATE green_beans SET ${sets.join(',')} WHERE id=?`).bind(...vals).run()
    if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  } catch (e) {
    if (isUniqueError(e)) return c.json({ success: false, error: DUP_BEAN_MSG }, 409)
    throw e
  }
  // 종류를 바꿨으면 이 생두의 모든 로스팅 기록도 같은 값으로 통일한다
  if (bt) await syncRoastUsageToBean(c.env.DB, gbId)
  return c.json({ success: true, item: await getGreenBean(c.env.DB, gbId) })
})

beanRoutes.delete('/api/green-beans/:id{[0-9]+}', async (c) => {
  const gbId = parseInt(c.req.param('id'), 10)
  if (c.req.query('hard') === '1') {
    const item = await getGreenBean(c.env.DB, gbId)
    if (!item) return c.json({ success: false, error: 'not found' }, 404)
    const remaining = parseFloat(item.remaining_kg) || 0
    if (remaining > 0.05)
      return c.json(
        { success: false, error: `재고가 ${remaining.toFixed(1)}kg 남아 있어 삭제할 수 없습니다. 먼저 숨김 처리하세요.` },
        400,
      )
    const db = c.env.DB
    const results = await db.batch([
      db.prepare('UPDATE coffees SET green_bean_id=NULL WHERE green_bean_id=?').bind(gbId),
      db.prepare('DELETE FROM blend_components WHERE green_bean_id=?').bind(gbId),
      db.prepare('DELETE FROM pricing WHERE green_bean_id=?').bind(gbId),
      db.prepare('DELETE FROM roasting_logs WHERE green_bean_id=?').bind(gbId),
      db.prepare('DELETE FROM purchases WHERE green_bean_id=?').bind(gbId),
      db.prepare('DELETE FROM green_beans WHERE id=?').bind(gbId),
    ])
    if (!(results[5].meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
    return c.json({ success: true })
  }
  const res = await c.env.DB.prepare("UPDATE green_beans SET status='단종' WHERE id=?").bind(gbId).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

beanRoutes.get('/api/green-beans/:id{[0-9]+}/for-coffee', async (c) => {
  const item = await getGreenBean(c.env.DB, parseInt(c.req.param('id'), 10))
  if (!item) return c.json({ success: false, error: 'not found' }, 404)
  const prefix = item.supplier_short ? `[${item.supplier_short}] ` : ''
  return c.json({
    success: true,
    name: prefix + item.name,
    process: item.process,
    cup_notes: item.cup_notes || '',
  })
})

// ---------- Purchases ----------

async function listPurchases(db: D1Database, gbId: number | null, limit = 200): Promise<Row[]> {
  let sql = `
      SELECT p.*, gb.name AS bean_name, gb.process AS process,
             gb.origin_country AS origin_country, gb.bean_type AS bean_type,
             s.short_name AS supplier_short
      FROM purchases p
      JOIN green_beans gb ON gb.id = p.green_bean_id
      LEFT JOIN suppliers s ON s.id = gb.supplier_id`
  const args: any[] = []
  if (gbId) { sql += ' WHERE p.green_bean_id = ?'; args.push(gbId) }
  sql += ' ORDER BY p.purchase_date DESC, p.id DESC LIMIT ?'
  args.push(limit)
  return (await db.prepare(sql).bind(...args).all<Row>()).results
}

beanRoutes.get('/api/purchases', async (c) => {
  const gbRaw = c.req.query('green_bean_id')
  return c.json({ success: true, items: await listPurchases(c.env.DB, gbRaw ? parseInt(gbRaw, 10) : null) })
})

beanRoutes.post('/api/purchases', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  for (const k of ['purchase_date', 'quantity_kg', 'unit_price'])
    if (!data[k]) return c.json({ success: false, error: `${k} 필수` }, 400)
  if (!data.green_bean_id && (!data.name || !data.process))
    return c.json({ success: false, error: '생두 선택 또는 원두명+가공방식 필수' }, 400)
  try {
    const gbId = await findOrCreateGreenBean(c.env.DB, data)
    const qty = parseFloat(data.quantity_kg)
    const price = parseInt(data.unit_price, 10)
    const discount = parseInt(data.discount || 0, 10) || 0
    const total = Math.trunc(qty * price) - discount
    const res = await c.env.DB
      .prepare(
        'INSERT INTO purchases (green_bean_id, purchase_date, quantity_kg, unit_price, discount, total_price, lot_number, notes) ' +
          'VALUES (?,?,?,?,?,?,?,?)',
      )
      .bind(gbId, data.purchase_date, qty, price, discount, total, data.lot_number ?? null, data.notes ?? null)
      .run()
    return c.json({ success: true, id: res.meta.last_row_id, green_bean_id: gbId })
  } catch (e: any) {
    if (e instanceof ValidationError) return c.json({ success: false, error: e.message }, 400)
    if (isUniqueError(e)) return c.json({ success: false, error: DUP_BEAN_MSG }, 409)
    throw e
  }
})

beanRoutes.put('/api/purchases/:id{[0-9]+}', async (c) => {
  const pid = parseInt(c.req.param('id'), 10)
  let data = (await c.req.json().catch(() => ({}))) as Row
  if (data.green_bean_id || (data.name && data.process)) {
    try {
      data = { ...data, green_bean_id: await findOrCreateGreenBean(c.env.DB, data) }
    } catch (e: any) {
      if (e instanceof ValidationError) return c.json({ success: false, error: e.message }, 400)
      if (isUniqueError(e)) return c.json({ success: false, error: DUP_BEAN_MSG }, 409)
      throw e
    }
  }
  const allowed = ['green_bean_id', 'purchase_date', 'quantity_kg', 'unit_price', 'discount', 'lot_number', 'notes']
  const sets: string[] = []
  const vals: any[] = []
  for (const k of allowed) if (k in data) { sets.push(`${k}=?`); vals.push(data[k]) }
  if ('quantity_kg' in data || 'unit_price' in data || 'discount' in data) {
    const row = await c.env.DB.prepare('SELECT * FROM purchases WHERE id=?').bind(pid).first<Row>()
    if (!row) return c.json({ success: false, error: 'not found' }, 404)
    const qty = parseFloat(data.quantity_kg ?? row.quantity_kg)
    const price = parseInt(data.unit_price ?? row.unit_price, 10)
    const disc = parseInt(data.discount ?? row.discount ?? 0, 10) || 0
    sets.push('total_price=?')
    vals.push(Math.trunc(qty * price) - disc)
  }
  if (!sets.length) return c.json({ success: false, error: 'not found' }, 404)
  vals.push(pid)
  const res = await c.env.DB.prepare(`UPDATE purchases SET ${sets.join(',')} WHERE id=?`).bind(...vals).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

beanRoutes.delete('/api/purchases/:id{[0-9]+}', async (c) => {
  const res = await c.env.DB.prepare('DELETE FROM purchases WHERE id=?').bind(parseInt(c.req.param('id'), 10)).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

// ---------- Roasting Logs ----------

/** 다양한 날짜 형식 → (연,월,일) (db.py _parse_ymd) */
function parseYmd(d: any): [number, number, number] {
  const m = String(d || '').match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/)
  return m ? [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)] : [0, 0, 0]
}
function normYmd(d: any): any {
  const [y, mo, da] = parseYmd(d)
  return y ? `${String(y).padStart(4, '0')}-${String(mo).padStart(2, '0')}-${String(da).padStart(2, '0')}` : d
}

async function listRoastingLogs(db: D1Database, gbId: number | null, limit = 1000): Promise<Row[]> {
  let sql = `
      SELECT r.*, gb.name AS bean_name, gb.cup_notes AS cup_notes,
             gb.process AS bean_process, gb.bean_type AS bean_type,
             s.short_name AS supplier_short,
             EXISTS(
                 SELECT 1 FROM coffees c
                 WHERE c.name = gb.name AND c.status IN ('예정','진행 중')
                   AND (c.serve_date IS NULL OR c.serve_date='' OR c.serve_date >= ?)
                   AND COALESCE(c.roast_date,'') >= COALESCE(r.roast_date,'')
             ) AS has_active_coffee
      FROM roasting_logs r
      JOIN green_beans gb ON gb.id = r.green_bean_id
      LEFT JOIN suppliers s ON s.id = gb.supplier_id`
  const args: any[] = [kstTodayISO()]
  if (gbId) { sql += ' WHERE r.green_bean_id = ?'; args.push(gbId) }
  const rows = (await db.prepare(sql).bind(...args).all<Row>()).results
  for (const r of rows) r.roast_date = normYmd(r.roast_date)
  // 정렬: 로스팅일 최신 → 배출량 미기입 먼저 → 배출 기입 시각 최신 → id (모두 내림차순)
  const key = (r: Row): [string, number, string, number] => [
    parseYmd(r.roast_date).map((n) => String(n).padStart(4, '0')).join('-'),
    r.output_weight_g == null ? 1 : 0,
    r.output_at || '',
    r.id || 0,
  ]
  rows.sort((a, b) => {
    const ka = key(a), kb = key(b)
    for (let i = 0; i < 4; i++) {
      if (ka[i] < kb[i]) return 1
      if (ka[i] > kb[i]) return -1
    }
    return 0
  })
  return rows.slice(0, limit)
}

beanRoutes.get('/api/roasting-logs', async (c) => {
  const gbRaw = c.req.query('green_bean_id')
  return c.json({ success: true, items: await listRoastingLogs(c.env.DB, gbRaw ? parseInt(gbRaw, 10) : null) })
})

const optFloat = (v: any): number | null => (v === null || v === undefined || v === '' ? null : parseFloat(v))

async function getRoastingLog(db: D1Database, rid: number): Promise<Row | null> {
  const row = await db.prepare('SELECT * FROM roasting_logs WHERE id=?').bind(rid).first<Row>()
  if (!row) return null
  row.roast_date = normYmd(row.roast_date)
  return row
}

/** 로스팅한 생두를 '오늘의 커피 예정'으로 등록 (app.py _ensure_scheduled_coffee)
 *  중복 판정은 이름 + 로트(로스팅일) 기준. 같은 날 여러 배치는 1건으로 묶이지만,
 *  제공 중인 묵은 로트가 새 로스팅분을 막지는 않는다. */
async function ensureScheduledCoffee(db: D1Database, greenBeanId: number, roastDate: string) {
  const bean = await getGreenBean(db, greenBeanId)
  if (!bean) return null
  const name = String(bean.name || '').trim()
  if (!name) return null
  // 블랜드 생두는 블렌딩 재료로만 쓰이므로 오늘의 커피로 등록하지 않는다.
  // 어느 경로로 들어와도 막히도록 생두 종류를 기준으로 여기서 한 번에 차단한다.
  if (normBeanType(bean.bean_type) === '블랜드') return { blocked: true, created: false, name }
  const lot = normYmd(roastDate)
  const existing = await findActiveByName(db, name, lot)
  if (existing) return { created: false, id: existing.id, name }
  const cid = await createCoffee(db, {
    name,
    roastery: '92도씨 로스터리',
    roast_date: lot,
    process: bean.process,
    cup_notes: bean.cup_notes,
    status: '예정',
    green_bean_id: greenBeanId,
  })
  return { created: true, id: cid, name }
}

beanRoutes.post('/api/roasting-logs', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  for (const k of ['green_bean_id', 'roast_date', 'input_weight_g'])
    if (!data[k]) return c.json({ success: false, error: `${k} 필수` }, 400)
  const inputG = parseFloat(data.input_weight_g)
  const actualG = optFloat(data.actual_input_weight_g)
  const outputG = optFloat(data.output_weight_g)
  const effIn = actualG !== null ? actualG : inputG
  const loss = outputG !== null && effIn > 0 ? Math.round((1 - outputG / effIn) * 10000) / 100 : null
  // 원두 종류의 창구는 생두 마스터 하나. 로스팅 폼에서 바꿔 보내면 생두에 반영하고
  // 그 생두의 기존 기록까지 같은 값으로 통일한다. 안 보내면 생두 종류를 그대로 물려받는다.
  const gbId0 = parseInt(data.green_bean_id, 10)
  const usageType = 'usage_type' in data
    ? await setBeanTypeFrom(c.env.DB, gbId0, data.usage_type)
    : normBeanType(
        (await c.env.DB.prepare('SELECT bean_type FROM green_beans WHERE id=?').bind(gbId0).first<Row>())?.bean_type,
      )
  // 블랜드는 블렌딩 재료로만 쓰이므로 오늘의 커피에 등록하지 않는다 (app.py 와 동일)
  const isBlend = usageType === '블랜드'
  const makeCoffee = !isBlend && (data.create_coffee ?? true) ? 1 : 0
  const outputAt = outputG !== null ? utcNowISO() : null
  const res = await c.env.DB
    .prepare(
      'INSERT INTO roasting_logs (green_bean_id, roast_date, input_weight_g, actual_input_weight_g, ' +
        'output_weight_g, moisture_loss_pct, roast_level, notes, coffee_id, make_coffee, usage_type, output_at) ' +
        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
    )
    .bind(
      parseInt(data.green_bean_id, 10), data.roast_date, inputG, actualG, outputG, loss,
      data.roast_level ?? null, data.notes ?? null, data.coffee_id ?? null, makeCoffee, usageType, outputAt,
    )
    .run()
  let coffee = null
  if (!isBlend && data.create_coffee && data.output_weight_g !== null && data.output_weight_g !== undefined && data.output_weight_g !== '')
    coffee = await ensureScheduledCoffee(c.env.DB, parseInt(data.green_bean_id, 10), data.roast_date)
  return c.json({ success: true, id: res.meta.last_row_id, coffee })
})

beanRoutes.post('/api/roasting-logs/:id{[0-9]+}/make-coffee', async (c) => {
  const rid = parseInt(c.req.param('id'), 10)
  const log = await getRoastingLog(c.env.DB, rid)
  if (!log) return c.json({ success: false, error: 'not found' }, 404)
  if (normBeanType(log.usage_type) === '블랜드')
    return c.json({ success: false, error: '블랜드용 로스팅은 오늘의 커피로 등록할 수 없습니다' }, 400)
  const coffee = await ensureScheduledCoffee(c.env.DB, log.green_bean_id, log.roast_date)
  if (!coffee) return c.json({ success: false, error: '생두 정보를 찾을 수 없음' }, 400)
  if (coffee.blocked)
    return c.json({ success: false, error: '블랜드 원두는 오늘의 커피로 등록할 수 없습니다' }, 400)
  await c.env.DB.prepare('UPDATE roasting_logs SET make_coffee=1 WHERE id=?').bind(rid).run()
  return c.json({ success: true, coffee })
})

beanRoutes.post('/api/roasting-logs/:id{[0-9]+}/unmake-coffee', async (c) => {
  const rid = parseInt(c.req.param('id'), 10)
  const log = await getRoastingLog(c.env.DB, rid)
  if (!log) return c.json({ success: false, error: 'not found' }, 404)
  const bean = log.green_bean_id ? await getGreenBean(c.env.DB, log.green_bean_id) : null
  const name = bean ? String(bean.name || '').trim() : ''
  let removed: Row | null = null
  // 그 로스팅일 로트만 정확히 지운다 — 이름만 보면 제공 중인 다른 로트를 지워버린다
  const existing = name ? await findActiveByName(c.env.DB, name, normYmd(log.roast_date), 'eq') : null
  if (existing) {
    await c.env.DB.prepare('DELETE FROM coffees WHERE id=?').bind(existing.id).run()
    removed = { name, status: existing.status }
  }
  await c.env.DB.prepare('UPDATE roasting_logs SET make_coffee=0 WHERE id=?').bind(rid).run()
  return c.json({ success: true, removed })
})

beanRoutes.put('/api/roasting-logs/:id{[0-9]+}', async (c) => {
  const rid = parseInt(c.req.param('id'), 10)
  const data = (await c.req.json().catch(() => ({}))) as Row
  const prev = await getRoastingLog(c.env.DB, rid)
  if (!prev) return c.json({ success: false, error: 'not found' }, 404)
  // 로스팅 폼에서 종류를 바꾸면 생두 마스터에 반영 → 그 생두의 모든 기록이 함께 통일된다.
  let usageAfter: string | null = null
  if ('usage_type' in data)
    usageAfter = await setBeanTypeFrom(c.env.DB, parseInt(data.green_bean_id ?? prev.green_bean_id, 10), data.usage_type)
  const isBlend = usageAfter === '블랜드'
  const allowed = ['green_bean_id', 'roast_date', 'input_weight_g', 'output_weight_g',
    'roast_level', 'notes', 'coffee_id', 'make_coffee']
  const sets: string[] = []
  const vals: any[] = []
  // 블랜드는 오늘의 커피 연동 불가 — 요청에 make_coffee 가 섞여 와도 꺼진 상태를 유지한다
  for (const k of allowed) if (k in data && !(isBlend && k === 'make_coffee')) { sets.push(`${k}=?`); vals.push(data[k]) }
  if (isBlend) { sets.push('make_coffee=?'); vals.push(0) }
  if ('input_weight_g' in data || 'output_weight_g' in data || 'actual_input_weight_g' in data) {
    const inp = parseFloat(data.input_weight_g ?? prev.input_weight_g)
    let actual: number | null
    if ('actual_input_weight_g' in data) {
      actual = optFloat(data.actual_input_weight_g)
      sets.push('actual_input_weight_g=?')
      vals.push(actual)
    } else actual = prev.actual_input_weight_g
    const eff = actual !== null && actual !== undefined ? actual : inp
    const outRaw = 'output_weight_g' in data ? data.output_weight_g : prev.output_weight_g
    const out = outRaw !== null && outRaw !== undefined ? parseFloat(outRaw) : null
    const loss = out !== null && eff > 0 ? Math.round((1 - out / eff) * 10000) / 100 : null
    sets.push('moisture_loss_pct=?')
    vals.push(loss)
    if ('output_weight_g' in data) {
      if (out === null) { sets.push('output_at=?'); vals.push(null) }
      else if (!prev.output_at) { sets.push('output_at=?'); vals.push(utcNowISO()) }
    }
  }
  // 종류만 바꾼 요청이면 이 기록 자체에 쓸 필드가 없을 수 있다 (생두 반영은 이미 끝남)
  if (!sets.length)
    return usageAfter !== null
      ? c.json({ success: true, coffee: null })
      : c.json({ success: false, error: 'not found' }, 404)
  vals.push(rid)
  await c.env.DB.prepare(`UPDATE roasting_logs SET ${sets.join(',')} WHERE id=?`).bind(...vals).run()
  // 배출량이 '처음' 기입되는 시점에 오늘의 커피 예정 자동 등록 (연동 ON 기록만)
  let coffee = null
  if (prev.output_weight_g == null && data.output_weight_g !== null && data.output_weight_g !== undefined && data.output_weight_g !== '') {
    const log = await getRoastingLog(c.env.DB, rid)
    // 블랜드용 로스팅은 배출량을 기입해도 오늘의 커피에 등록하지 않는다
    if (log && log.make_coffee && normBeanType(log.usage_type) !== '블랜드')
      coffee = await ensureScheduledCoffee(c.env.DB, log.green_bean_id, log.roast_date)
  }
  return c.json({ success: true, coffee })
})

beanRoutes.delete('/api/roasting-logs/:id{[0-9]+}', async (c) => {
  const res = await c.env.DB.prepare('DELETE FROM roasting_logs WHERE id=?').bind(parseInt(c.req.param('id'), 10)).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

// ---------- Inventory ----------

beanRoutes.get('/api/inventory', async (c) => {
  const sql = `
      SELECT gb.id, gb.name, gb.process, gb.grade, gb.bean_type, gb.is_decaf, gb.status, gb.hidden,
          gb.sold_out,
          s.name AS supplier_name, s.short_name AS supplier_short,
          COALESCE(p_sum.purchased_kg, 0) AS purchased_kg,
          COALESCE(r_sum.used_kg, 0) AS used_kg,
          COALESCE(p_sum.purchased_kg, 0) - COALESCE(r_sum.used_kg, 0)
              + COALESCE(gb.stock_adjustment_kg, 0) AS remaining_kg,
          COALESCE(p_sum.avg_unit_price, 0) AS avg_unit_price,
          p_sum.last_purchase_date
      FROM green_beans gb
      LEFT JOIN suppliers s ON s.id = gb.supplier_id
      LEFT JOIN (
          SELECT green_bean_id, SUM(quantity_kg) AS purchased_kg,
                 ROUND(CAST(SUM(total_price) AS REAL) / NULLIF(SUM(quantity_kg), 0)) AS avg_unit_price,
                 MAX(purchase_date) AS last_purchase_date
          FROM purchases GROUP BY green_bean_id
      ) p_sum ON p_sum.green_bean_id = gb.id
      LEFT JOIN (
          SELECT green_bean_id, SUM(input_weight_g) / 1000.0 AS used_kg
          FROM roasting_logs GROUP BY green_bean_id
      ) r_sum ON r_sum.green_bean_id = gb.id
      WHERE gb.status = '활성'
      ORDER BY
          (COALESCE(p_sum.purchased_kg,0) - COALESCE(r_sum.used_kg,0)
              + COALESCE(gb.stock_adjustment_kg,0)) ASC,
          p_sum.last_purchase_date DESC`
  const cutoff = monthsAgoISO(12)
  const { results } = await c.env.DB.prepare(sql).all<Row>()
  for (const d of results) {
    const lpd = d.last_purchase_date || ''
    d.is_stale = d.remaining_kg <= 0 && lpd < cutoff ? 1 : 0
    if (d.remaining_kg < 0) d.remaining_kg = 0
  }
  return c.json({ success: true, items: results })
})

// ---------- Pricing ----------

async function listPricing(db: D1Database, gbId: number | null): Promise<Row[]> {
  let sql = `
      SELECT pr.*, gb.name AS bean_name, s.short_name AS supplier_short
      FROM pricing pr
      JOIN green_beans gb ON gb.id = pr.green_bean_id
      LEFT JOIN suppliers s ON s.id = gb.supplier_id`
  const args: any[] = []
  if (gbId) { sql += ' WHERE pr.green_bean_id = ?'; args.push(gbId) }
  sql += ' ORDER BY gb.name, pr.weight_g'
  return (await db.prepare(sql).bind(...args).all<Row>()).results
}

beanRoutes.get('/api/pricing', async (c) => {
  const gbRaw = c.req.query('green_bean_id')
  return c.json({ success: true, items: await listPricing(c.env.DB, gbRaw ? parseInt(gbRaw, 10) : null) })
})

beanRoutes.post('/api/pricing', async (c) => {
  const data = (await c.req.json().catch(() => ({}))) as Row
  for (const k of ['green_bean_id', 'weight_g', 'retail_price'])
    if (!data[k]) return c.json({ success: false, error: `${k} 필수` }, 400)
  const res = await c.env.DB
    .prepare(
      'INSERT INTO pricing (green_bean_id, weight_g, retail_price, wholesale_price) VALUES (?,?,?,?) ' +
        'ON CONFLICT(green_bean_id, weight_g) DO UPDATE SET retail_price=excluded.retail_price, ' +
        "wholesale_price=excluded.wholesale_price, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
    )
    .bind(
      parseInt(data.green_bean_id, 10), parseInt(data.weight_g, 10),
      parseInt(data.retail_price, 10), data.wholesale_price ?? null,
    )
    .run()
  return c.json({ success: true, id: res.meta.last_row_id })
})

beanRoutes.delete('/api/pricing/:id{[0-9]+}', async (c) => {
  const res = await c.env.DB.prepare('DELETE FROM pricing WHERE id=?').bind(parseInt(c.req.param('id'), 10)).run()
  if (!(res.meta.changes ?? 0)) return c.json({ success: false, error: 'not found' }, 404)
  return c.json({ success: true })
})

beanRoutes.get('/api/pricing/cost-analysis/:id{[0-9]+}', async (c) => {
  const gbId = parseInt(c.req.param('id'), 10)
  const gb = await getGreenBean(c.env.DB, gbId)
  if (!gb) return c.json({ success: false, error: 'not found' }, 404)
  const avgPrice = gb.avg_unit_price || 0
  const avgLoss = gb.avg_loss_pct || 0
  const yieldRatio = avgLoss < 100 ? (100 - avgLoss) / 100 : 0
  const roastedCostPerKg = yieldRatio > 0 ? Math.trunc(avgPrice / yieldRatio) : 0
  const roastedCostPerG = roastedCostPerKg ? Math.round((roastedCostPerKg / 1000) * 100) / 100 : 0
  return c.json({
    success: true,
    green_bean: gb,
    avg_green_cost_per_kg: avgPrice,
    avg_loss_pct: Math.round(avgLoss * 100) / 100,
    yield_ratio: Math.round(yieldRatio * 10000) / 10000,
    roasted_cost_per_kg: roastedCostPerKg,
    roasted_cost_per_g: roastedCostPerG,
    espresso_20g_cost: Math.round(roastedCostPerG * 20),
    pricing: await listPricing(c.env.DB, gbId),
  })
})

// ---------- 공개 읽기 전용 ----------
// 원두 카드(/beans)와 인쇄 스크립트가 공개 노출 상태를 가져가는 창구.
// 관리자에서 바꾼 값이 그대로 공개 페이지에 반영된다.
// 위 requirePin 가드 목록에 /api/beans 는 없으므로 인증 없이 열린다.
//
//   sold_out — 품절. 카드는 남기되 배지를 달고 목록 맨 뒤로 밀린다.
//   blend    — 블랜드. 산지 소개가 아니라 우리 배합이므로 카드에서 아예 뺀다.
//              (오늘의 커피 등록 불가와 같은 이유. 창구는 green_beans.bean_type 하나)
beanRoutes.get('/api/beans/status', async (c) => {
  const { results } = await c.env.DB
    .prepare(
      "SELECT id, sold_out, bean_type FROM green_beans WHERE status='활성' " +
        "AND (sold_out=1 OR bean_type='블랜드') ORDER BY id",
    )
    .all<Row>()
  return c.json({
    success: true,
    sold_out: results.filter((r) => r.sold_out).map((r) => r.id),
    blend: results.filter((r) => r.bean_type === '블랜드').map((r) => r.id),
  })
})
