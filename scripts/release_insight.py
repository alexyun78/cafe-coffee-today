"""Coffee Insight 백로그 릴리스 워커 — 토큰 0 (LLM 호출 없음).

미리 작성해 둔 사이드카(content/insight_queue/*.json) 중 다음 1편을 꺼내
'오늘' 날짜로 발행(렌더)한다. Claude API 도 Google Drive 도 거치지 않으므로
운영 비용이 0 이다. 글 작성은 Cowork 대화(구독)에서 미리 해 큐에 쌓아둔다.

흐름:
  1. 오늘 날짜(KST) 결정 (또는 --date)
  2. 같은 날짜 발행분이 이미 index 에 있으면 생략 (수동 백필/재실행 충돌 방지)
  3. 큐에서 파일명 정렬상 가장 앞선 사이드카 1개 선택
  4. normalize(date/id/slug 정규화) → 필수 필드 검증
  5. ingest_insights.process_one 으로 렌더(HTML/JSON) + index.json 갱신
  6. 발행한 큐 파일 삭제 (재사용 방지)
  7. (commit/push 는 release.sh 래퍼가 처리)

의존성: jinja2 (+ ingest_insights 가 import 하는 requests). anthropic 불필요.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# 렌더·인덱스 로직은 ingest_insights 의 것을 그대로 재사용 (generate 와 동일 템플릿)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest_insights as ing

KST = timezone(timedelta(hours=9))
QUEUE_DIR = ing.REPO_ROOT / "content" / "insight_queue"

# trivia 일러스트 토픽 키 (ingest_insights.TRIVIA_HERO 기준)
TRIVIA_TOPICS = [
    "origin", "processing", "trend", "terms", "decaf",
    "bestcup", "competition", "trade",
]

# 필수 필드 (generate_insight 와 동일 기준)
REQUIRED_COMMON = ["title_ko", "one_liner", "categories_primary", "glossary",
                   "easy_hero_title", "easy_intro_paragraphs", "easy_findings"]
REQUIRED_PAPER = ["title_original", "authors", "journal", "pub_date", "doi",
                  "summary", "key_findings", "implications"]
REQUIRED_TRIVIA = ["topic"]


def log(msg: str) -> None:
    sys.stdout.write(f"[release] {msg}\n")
    sys.stdout.flush()


def err(msg: str) -> None:
    sys.stderr.write(f"[release] ERROR: {msg}\n")
    sys.stderr.flush()


def sanitize_slug(slug: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9\-]+", "-", (slug or "").lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or fallback


def normalize(payload: dict, kind: str, date_str: str) -> dict:
    payload["type"] = "trivia" if kind == "trivia" else "paper"
    payload["date"] = date_str
    payload["version"] = payload.get("version") or 1
    slug = sanitize_slug(payload.get("slug", ""), f"{kind}-{date_str}")
    payload["slug"] = slug
    payload["id"] = f"{date_str}-{slug}"
    if kind == "paper":
        payload["source_basis"] = payload.get("source_basis") or "abstract_only"
        payload.setdefault("links", {})
        if payload.get("doi") and not payload["links"].get("doi"):
            payload["links"]["doi"] = f"https://doi.org/{payload['doi']}"
    else:
        payload.setdefault("categories_primary", ["커피 상식"])
        payload.setdefault("links", {})
    return payload


def validate(payload: dict, kind: str) -> list[str]:
    missing = [k for k in REQUIRED_COMMON if not payload.get(k)]
    extra = REQUIRED_PAPER if kind == "paper" else REQUIRED_TRIVIA
    missing += [k for k in extra if not payload.get(k)]
    if kind == "trivia" and payload.get("topic") not in TRIVIA_TOPICS:
        missing.append(f"topic(invalid:{payload.get('topic')})")
    return missing


def queue_files() -> list[Path]:
    if not QUEUE_DIR.exists():
        return []
    return sorted(p for p in QUEUE_DIR.glob("*.json"))


def build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ing.TEMPLATE_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        keep_trailing_newline=False,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--dry", action="store_true",
                    help="렌더만 /tmp 로 확인. index·큐 변경 없음")
    ap.add_argument("--list", action="store_true", help="큐 목록만 출력하고 종료")
    args = ap.parse_args()

    files = queue_files()
    if args.list:
        log(f"큐 {len(files)}편:")
        for p in files:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                log(f"  - {p.name}: [{d.get('type','?')}/{d.get('topic','-')}] {d.get('title_ko','')[:40]}")
            except ValueError:
                log(f"  - {p.name}: (JSON 파싱 실패)")
        return 0

    date_str = args.date or datetime.now(KST).strftime("%Y-%m-%d")

    index = ing.read_index()
    if not args.dry:
        for it in (index.get("items") or []):
            if it.get("date") == date_str:
                log(f"이미 {date_str} 발행분 있음({it.get('id')}) — 릴리스 생략")
                return 0

    if not files:
        err("큐가 비었음 — content/insight_queue/ 보충 필요. 오늘 발행 없음.")
        return 0  # 타이머가 실패로 표시되지 않도록 0 반환 (발행만 안 됨)

    qf = files[0]
    try:
        payload = json.loads(qf.read_text(encoding="utf-8"))
    except ValueError as e:
        err(f"{qf.name} JSON 파싱 실패: {e}")
        return 3

    kind = payload.get("type") or "trivia"
    payload = normalize(payload, kind, date_str)
    missing = validate(payload, kind)
    if missing:
        err(f"{qf.name} 필수 필드 누락: {missing}")
        return 4

    env = build_env()

    if args.dry:
        html = ing.render_html(payload, env)
        out = Path("/tmp") / f"{payload['id']}.html"
        out.write_text(html, encoding="utf-8")
        log(f"[dry] 렌더 OK → {out} ({len(html)} bytes) | id={payload['id']} "
            f"| title={payload.get('title_ko')}")
        return 0

    summary = ing.process_one(payload, env)
    if not summary:
        err("렌더 실패")
        return 5

    index.setdefault("items", []).append(summary)
    index["items"].sort(
        key=lambda x: (x.get("date") or "", x.get("id") or ""), reverse=True
    )
    ing.write_index(index)

    # 발행한 큐 파일 삭제 (git rm 효과는 release.sh 의 git add -A 가 처리)
    qf.unlink()
    remaining = len(queue_files())
    log(f"발행 완료: {payload['id']} ({payload.get('title_ko')}) | 큐 잔여 {remaining}편")
    if remaining <= 3:
        log(f"⚠️ 큐 잔여 {remaining}편 — 곧 보충 필요")
    return 0


if __name__ == "__main__":
    sys.exit(main())
