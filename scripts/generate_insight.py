"""Coffee Insight 자체 생성 워커 — Claude API + 서버 웹검색으로 매일 1편 생성.

기존 파이프라인(claude.ai 루틴 → Google Drive → ingest)의 Drive 의존을 제거한 대체 경로.
이 스크립트는 서버 systemd 타이머(cafe-coffee-generate.timer)가 매일 호출한다.

흐름:
  1. 오늘 날짜(KST) + 요일로 글 종류 결정 (화목토일=paper, 월수금=trivia)
  2. index.json 에서 최근 제목·토픽·DOI 수집 → 중복 회피 컨텍스트
  3. Claude API 호출 (서버 web_search 툴 사용):
     - paper : 실제 최근 커피 논문을 웹검색으로 찾아 abstract 기반 사이드카 JSON 생성
               (가짜 DOI 금지 — 반드시 실재 논문)
     - trivia: 상록 주제로 친근 에세이 사이드카 JSON 생성 (신선도 필요 주제는 검색 후 확인)
  4. 최종 응답에서 JSON 추출 → 필수 필드 검증 → id/date/type/slug 정규화
  5. ingest_insights.process_one 으로 렌더(HTML/JSON) + index.json 갱신
  6. (commit/push 는 generate.sh 래퍼가 처리)

환경(.env / systemd EnvironmentFile):
  ANTHROPIC_API_KEY    — 필수
  INSIGHT_MODEL        — 선택(기본 claude-opus-4-8)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ingest_insights 의 렌더·인덱스 로직을 그대로 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest_insights as ing

KST = timezone(timedelta(hours=9))
DEFAULT_MODEL = "claude-opus-4-8"

# 요일(월=0 … 일=6) → 글 종류. 화목토일=paper, 월수금=trivia.
PAPER_WEEKDAYS = {1, 3, 5, 6}

# hero 매핑이 인식하는 카테고리 라벨 (ingest_insights.CATEGORY_HERO 기준)
ALLOWED_CATEGORIES = [
    "생두", "로스팅", "추출", "향미/관능", "화학/분석화학",
    "건강/영양", "지속가능성/경제", "장비/공학", "미생물", "시장/소비자",
]
# trivia 일러스트 토픽 키 (ingest_insights.TRIVIA_HERO 기준)
TRIVIA_TOPICS = [
    "origin", "processing", "trend", "terms", "decaf",
    "bestcup", "competition", "trade",
]
# 신선도가 필요해 웹검색 확인이 필요한 trivia 토픽
TRIVIA_FRESH = {"competition", "trade", "bestcup", "trend"}


def log(msg: str) -> None:
    sys.stdout.write(f"[generate] {msg}\n")
    sys.stdout.flush()


def err(msg: str) -> None:
    sys.stderr.write(f"[generate] ERROR: {msg}\n")
    sys.stderr.flush()


def recent_context(index: dict, limit: int = 30) -> dict:
    """최근 항목에서 중복 회피용 제목/토픽/DOI 목록 추출."""
    items = (index.get("items") or [])[:limit]
    titles, topics, dois = [], [], []
    for it in items:
        if it.get("title_ko"):
            titles.append(it["title_ko"])
    # 토픽/DOI 는 index 요약에 없으므로 개별 JSON 에서 읽는다
    for it in items:
        pid = it.get("id")
        if not pid:
            continue
        p = ing.INSIGHTS_DIR / f"{pid}.json"
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("topic"):
            topics.append(payload["topic"])
        if payload.get("doi"):
            dois.append(payload["doi"])
    return {"titles": titles, "topics": topics, "dois": dois}


SCHEMA_COMMON = """공통 필수 필드:
- "id": "" (비워둬 — 서버가 채움)
- "slug": 영문 kebab-case 5~8단어 (예: "coffee-fermentation-yeast-aroma")
- "title_ko": 한국어 제목 (질문형 권장)
- "one_liner": 한 줄 요약 (반말 OK)
- "categories_primary": [라벨 1개], "categories_secondary": [라벨 0~2개]
- 친근 필드(반드시 반말+비유): "easy_hero_emoji", "easy_hero_title"(질문형),
  "easy_intro_paragraphs"(2~3개), "easy_concepts"(2~4개; 각 {title, body, analogy}),
  "easy_findings"(3~4개; 각 {medal:"gold|silver|bronze|medal", title, body}),
  "easy_tables"(0~1개; {title, headers[], rows[[]]}), "easy_summary"
- "glossary": 5~6개; 각 {term, ko} — 어려운 말 풀이 (반드시 채움)
- "data_charts": [] 또는 [{title, unit, x_labels:[...], values:[숫자...]}] (실제 숫자 있을 때만)
"""

PAPER_SCHEMA = """type="paper" 추가 필수 필드:
- "type": "paper"
- "title_original": 논문 원제(영문)
- "authors": "First et al." 형식
- "journal": 저널명, "pub_date": "YYYY-MM" 또는 "YYYY-MM-DD"
- "doi": 실제 DOI (반드시 웹검색으로 확인한 실재 값 — 절대 지어내지 말 것)
- "summary": 학술 요약 1문단(한국어)
- "key_findings": 핵심 발견 4~6개(한국어 배열)
- "implications": {"농가/가공장": "...", "로스터/큐그레이더": "...", "R&D": "..."}
- "limitations": 한계(한국어)
- "citation_apa": APA 인용
- "links": {"doi": "https://doi.org/...", "oa_pdf": "", "journal_homepage": "..."}
- "source_basis": "abstract_only"
"""

TRIVIA_SCHEMA = """type="trivia" 추가 필수 필드:
- "type": "trivia"
- "topic": 다음 중 하나 — origin/processing/trend/terms/decaf/bestcup/competition/trade
- "categories_primary": ["커피 상식"], "categories_secondary": [한글 라벨 1개]
- "links": {} (출처 링크 있으면 {"source": "https://..."} 가능)
학술 필드(summary/key_findings/implications/doi 등)는 넣지 않는다.
"""


def build_system() -> str:
    return (
        "너는 92도씨 커피의 '오늘의 커피 인사이트' 콘텐츠 작가야. "
        "중고생도 이해할 친근한 한국어(반말, 호기심 자극, 일상 비유: 김치 발효·빵 효모·강한 불 vs 약불 등)로 쓴다. "
        "출력은 오직 하나의 JSON 객체. 마크다운 코드펜스·설명·서론 없이 '{' 로 시작해 '}' 로 끝난다. "
        "한국어 텍스트 안의 큰따옴표는 쓰지 말고 작은따옴표('…')를 써서 JSON 이 깨지지 않게 해라."
    )


def build_user_prompt(kind: str, date_str: str, ctx: dict) -> str:
    avoid_titles = "\n".join(f"- {t}" for t in ctx["titles"][:20]) or "(없음)"
    if kind == "paper":
        avoid_dois = ", ".join(ctx["dois"][:20]) or "(없음)"
        return f"""오늘({date_str}) '오늘의 커피 인사이트' 논문 분석 1편을 만든다.

먼저 web_search 로 **실제로 존재하는 최근(가급적 2025~2026년) 커피 과학 논문**을 한 편 찾아라.
- 주제 풀: 발효/가공·향미화학·로스팅·생두/품종·추출·건강/영양·지속가능성·분석기술(ML/분광) 등 다양하게.
- 반드시 **실재하는 논문**이어야 하고, **DOI·저널·저자·발표연월을 웹검색으로 확인**해라. 확신이 안 서면 다른 논문을 찾아라. 절대 지어내지 마라.
- 아래 최근 제목/DOI 와 **겹치지 않는** 새 논문을 골라라.

최근 제목(피할 것):
{avoid_titles}

최근 DOI(피할 것): {avoid_dois}

그다음, 그 논문의 abstract 를 근거로 아래 스키마의 사이드카 JSON 을 작성해라(source_basis="abstract_only").
카테고리 라벨은 다음에서만 고른다: {", ".join(ALLOWED_CATEGORIES)}

{SCHEMA_COMMON}
{PAPER_SCHEMA}

최종 메시지는 JSON 객체 하나만 출력한다."""
    else:  # trivia
        avoid_topics = ", ".join(ctx["topics"][:20]) or "(없음)"
        return f"""오늘({date_str}) '오늘의 커피 상식' 친근 에세이 1편을 만든다.

토픽을 하나 고른다(최근 쓴 토픽은 피한다): origin/processing/trend/terms/decaf/bestcup/competition/trade
- 최근 사용 토픽(피할 것): {avoid_topics}
- 신선도가 필요한 토픽(competition·trade·bestcup·trend)을 고르면 **web_search 로 사실을 확인**하고,
  불확실하면 상록 토픽(origin·processing·terms·decaf)으로 대체해라(추측 금지).
- 상록 토픽은 검색 없이 도메인 지식으로 정확히 써도 된다.

카테고리: categories_primary=["커피 상식"], categories_secondary=[적절한 한글 라벨 1개]

{SCHEMA_COMMON}
{TRIVIA_SCHEMA}

최종 메시지는 JSON 객체 하나만 출력한다."""


def call_model(client, model: str, system: str, user_prompt: str) -> str:
    """web_search 툴을 허용한 메시지 루프. 최종 어시스턴트 텍스트를 반환."""
    tools = [{"type": "web_search_20260209", "name": "web_search"}]
    messages = [{"role": "user", "content": user_prompt}]
    for _ in range(6):  # pause_turn 안전장치
        resp = client.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=messages,
            tools=tools,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        # end_turn (또는 그 외) — 텍스트 블록을 모은다
        return "".join(b.text for b in resp.content if b.type == "text")
    return ""


def extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    i = text.find("{")
    j = text.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(text[i : j + 1])
    except ValueError:
        return None


def sanitize_slug(slug: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9\-]+", "-", (slug or "").lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or fallback


def normalize(payload: dict, kind: str, date_str: str, ctx: dict) -> dict:
    payload["type"] = "trivia" if kind == "trivia" else "paper"
    payload["date"] = date_str
    payload["version"] = payload.get("version") or 1
    slug = sanitize_slug(payload.get("slug", ""), f"{kind}-{date_str}")
    payload["slug"] = slug
    payload["id"] = f"{date_str}-{slug}"
    if kind == "paper":
        payload["source_basis"] = "abstract_only"
        payload.setdefault("links", {})
        if payload.get("doi") and not payload["links"].get("doi"):
            payload["links"]["doi"] = f"https://doi.org/{payload['doi']}"
    else:
        payload.setdefault("categories_primary", ["커피 상식"])
        payload.setdefault("links", {})
    return payload


REQUIRED_COMMON = ["title_ko", "one_liner", "categories_primary", "glossary",
                   "easy_hero_title", "easy_intro_paragraphs", "easy_findings"]
REQUIRED_PAPER = ["title_original", "authors", "journal", "pub_date", "doi",
                  "summary", "key_findings", "implications"]
REQUIRED_TRIVIA = ["topic"]


def validate(payload: dict, kind: str) -> list[str]:
    missing = [k for k in REQUIRED_COMMON if not payload.get(k)]
    extra = REQUIRED_PAPER if kind == "paper" else REQUIRED_TRIVIA
    missing += [k for k in extra if not payload.get(k)]
    if kind == "trivia" and payload.get("topic") not in TRIVIA_TOPICS:
        missing.append(f"topic(invalid:{payload.get('topic')})")
    return missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--type", choices=["paper", "trivia"], help="요일 규칙 대신 강제")
    args = ap.parse_args()

    if args.date:
        date_str = args.date
        d = datetime.fromisoformat(date_str)
    else:
        d = datetime.now(KST)
        date_str = d.strftime("%Y-%m-%d")
    kind = args.type or ("paper" if d.weekday() in PAPER_WEEKDAYS else "trivia")
    log(f"날짜 {date_str} ({d.strftime('%A')}) → 종류 {kind}")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        err("ANTHROPIC_API_KEY 미설정")
        return 2
    model = os.environ.get("INSIGHT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    index = ing.read_index()
    known_ids = {it.get("id") for it in (index.get("items") or [])}
    # 같은 날짜에 이미 같은 종류가 있으면 중복 생성 방지
    for it in (index.get("items") or []):
        if it.get("date") == date_str and (it.get("type") or "paper") == kind:
            log(f"이미 존재({it.get('id')}) — 생성 생략")
            return 0

    ctx = recent_context(index)
    client = anthropic.Anthropic(api_key=api_key)
    system = build_system()
    user_prompt = build_user_prompt(kind, date_str, ctx)

    payload = None
    for attempt in range(2):
        log(f"모델 호출 (model={model}, attempt={attempt + 1})")
        text = call_model(client, model, system, user_prompt)
        payload = extract_json(text)
        if not payload:
            err("JSON 추출 실패 — 재시도")
            user_prompt += "\n\n주의: 직전 출력이 유효한 JSON 이 아니었다. JSON 객체 하나만, '{' 로 시작해라."
            continue
        payload = normalize(payload, kind, date_str, ctx)
        missing = validate(payload, kind)
        if not missing:
            break
        err(f"필수 필드 누락: {missing} — 재시도")
        user_prompt += f"\n\n주의: 다음 필드가 비어 있었다: {missing}. 모두 채워라."
        payload = None

    if not payload:
        err("유효한 payload 생성 실패")
        return 3
    if payload["id"] in known_ids:
        log(f"id 중복({payload['id']}) — 생략")
        return 0

    env = Environment(
        loader=FileSystemLoader(str(ing.TEMPLATE_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        keep_trailing_newline=False,
    )
    summary = ing.process_one(payload, env)
    if not summary:
        err("렌더 실패")
        return 4
    index.setdefault("items", []).append(summary)
    index["items"].sort(
        key=lambda x: (x.get("date") or "", x.get("id") or ""), reverse=True
    )
    ing.write_index(index)
    log(f"생성 완료: {payload['id']} ({payload.get('title_ko')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
