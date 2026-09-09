// 원두 카드 목록 — static/beans/index.json 을 **번들에 넣어** 읽는다.
//
// 왜 자산(ASSETS)이 아니라 import 인가: 미션 원두는 잠겨 있어야 하는데, 브라우저가
// index.json 을 직접 받아갈 수 있으면 잠금이 무의미하다. 그래서 그 파일은
// .assetsignore 로 웹 서빙에서 빼고, Worker 만 번들로 들고 있는다.
// 원두를 추가·수정하는 방법은 그대로 static/beans/index.json 편집이다.
import beansIndex from '../../static/beans/index.json'
import { Env, Row } from './util'

export type BeanCard = Row & { id: string; green_bean_id?: number; name_ko?: string }

export const BEAN_CARDS: BeanCard[] = ((beansIndex as any).items || []) as BeanCard[]

const BY_ID = new Map(BEAN_CARDS.map((b) => [String(b.id), b]))

export const beanById = (id: string): BeanCard | null => BY_ID.get(String(id)) || null

/** 카드 목록에서 잠금 여부와 무관하게 늘 노출해도 되는 요약 (관리자 화면용) */
export const beanBrief = (b: BeanCard) => ({
  id: b.id,
  name_ko: b.name_ko ?? '',
  country: b.country ?? '',
  process: b.process ?? '',
  green_bean_id: b.green_bean_id ?? null,
})

/** 활성 미션 원두 id 목록 — 카드 목록에 실제로 존재하는 것만 (순서 지정 그대로) */
export async function activeMissionIds(db: D1Database): Promise<string[]> {
  const { results } = await db
    .prepare('SELECT bean_id FROM bean_missions WHERE active=1 ORDER BY sort_order, bean_id')
    .all<Row>()
  return results.map((r) => String(r.bean_id)).filter((id) => BY_ID.has(id))
}

/** 회원이 연 원두 id 집합 */
export async function unlockedIds(db: D1Database, memberId: number | null): Promise<Set<string>> {
  if (!memberId) return new Set()
  const { results } = await db
    .prepare('SELECT bean_id FROM bean_unlocks WHERE member_id=?')
    .bind(memberId)
    .all<Row>()
  return new Set(results.map((r) => String(r.bean_id)))
}

/** 품절·블랜드 (기존 /api/beans/status 와 같은 기준) */
export async function beanStatus(env: Env): Promise<{ soldOut: Set<number>; blend: Set<number> }> {
  const { results } = await env.DB.prepare(
    "SELECT id, sold_out, bean_type FROM green_beans WHERE status='활성' AND (sold_out=1 OR bean_type='블랜드')",
  ).all<Row>()
  return {
    soldOut: new Set(results.filter((r) => r.sold_out).map((r) => Number(r.id))),
    blend: new Set(results.filter((r) => r.bean_type === '블랜드').map((r) => Number(r.id))),
  }
}
