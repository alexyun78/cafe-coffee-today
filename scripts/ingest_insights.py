"""Coffee Insight 인제스트 워커 — GitHub Actions에서 매일 1회 실행.

흐름:
  1. Google Drive OAuth (refresh token 으로 access token 발급)
  2. `cafe-insight YYYY-MM-DD — *` 패턴의 Drive 파일 검색
  3. 이미 처리된 id 는 건너뜀 (static/insights/index.json 기준)
  4. 각 미처리 파일에 대해:
     - 본문 다운로드 → JSON 파싱
     - PDF URL 있으면 다운로드 → PyMuPDF 로 그림 추출
     - data_charts → 빠른 SVG 차트는 viewer 가 처리하므로 PNG 생성은 선택적
     - Jinja2 로 standalone HTML 생성
     - static/insights/<id>.json + .html 저장
  5. static/insights/index.json 업데이트
  6. (스크립트 자체는 commit/push 하지 않음 — workflow YAML 이 마지막에 처리)

환경:
  - 표준 라이브러리만 가능한 한 사용
  - 외부 의존: requests, jinja2, PyMuPDF (figure 추출용)

비공개 secrets (GitHub Actions secret 또는 env):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ---- 경로 ----
REPO_ROOT = Path(__file__).resolve().parent.parent
INSIGHTS_DIR = REPO_ROOT / "static" / "insights"
FIGURES_ROOT = REPO_ROOT / "static" / "img" / "insights" / "articles"
TEMPLATE_DIR = Path(__file__).resolve().parent
INDEX_FILE = INSIGHTS_DIR / "index.json"

# ---- 카테고리 → hero 이미지 매핑 ----
CATEGORY_HERO = {
    "생두": "/static/img/insights/hero/green-bean.svg",
    "로스팅": "/static/img/insights/hero/roasting.svg",
    "추출": "/static/img/insights/hero/extraction.svg",
    "향미": "/static/img/insights/hero/flavor.svg",
    "향미/관능": "/static/img/insights/hero/flavor.svg",
    "관능": "/static/img/insights/hero/flavor.svg",
    "화학": "/static/img/insights/hero/chemistry.svg",
    "분석화학": "/static/img/insights/hero/chemistry.svg",
    "건강": "/static/img/insights/hero/health.svg",
    "영양": "/static/img/insights/hero/health.svg",
    "건강/영양": "/static/img/insights/hero/health.svg",
    "지속가능성": "/static/img/insights/hero/sustainability.svg",
    "지속가능성/경제": "/static/img/insights/hero/sustainability.svg",
    "장비": "/static/img/insights/hero/equipment.svg",
    "장비/공학": "/static/img/insights/hero/equipment.svg",
    "공학": "/static/img/insights/hero/equipment.svg",
    "미생물": "/static/img/insights/hero/microbiology.svg",
    "미생물학": "/static/img/insights/hero/microbiology.svg",
    "시장": "/static/img/insights/hero/market.svg",
    "소비자": "/static/img/insights/hero/market.svg",
    "시장/소비자": "/static/img/insights/hero/market.svg",
}
DEFAULT_HERO = "/static/img/insights/hero/default.svg"

# ---- Drive API ----
DRIVE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
INSIGHT_FILE_PREFIX = "cafe-insight"


def log(msg: str) -> None:
    sys.stdout.write(f"[ingest] {msg}\n")
    sys.stdout.flush()


def err(msg: str) -> None:
    sys.stderr.write(f"[ingest] ERROR: {msg}\n")
    sys.stderr.flush()


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Refresh token → access token."""
    r = requests.post(
        DRIVE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def drive_search_files(access_token: str) -> list[dict]:
    """이름이 `cafe-insight` 로 시작하는 모든 파일."""
    headers = {"Authorization": f"Bearer {access_token}"}
    files: list[dict] = []
    page_token = None
    while True:
        params = {
            "q": f"name contains '{INSIGHT_FILE_PREFIX}' and trashed=false",
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime)",
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get(DRIVE_FILES_URL, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        body = r.json()
        files.extend(body.get("files", []))
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    # 이름 패턴 검증
    pattern = re.compile(rf"^{INSIGHT_FILE_PREFIX}\s+\d{{4}}-\d{{2}}-\d{{2}}\s+—")
    return [f for f in files if pattern.match(f["name"])]


def drive_download_text(file_meta: dict, access_token: str) -> str:
    """Drive 파일 본문을 텍스트로. Google Doc 은 export, plain 은 download."""
    headers = {"Authorization": f"Bearer {access_token}"}
    file_id = file_meta["id"]
    mime = file_meta.get("mimeType", "")
    if mime == "application/vnd.google-apps.document":
        url = f"{DRIVE_FILES_URL}/{file_id}/export"
        params = {"mimeType": "text/plain"}
        r = requests.get(url, params=params, headers=headers, timeout=30)
    else:
        url = f"{DRIVE_FILES_URL}/{file_id}"
        params = {"alt": "media"}
        r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    # Drive 가 BOM 또는 추가 가공 없이 반환
    return r.content.decode("utf-8", errors="replace")


def read_index() -> dict:
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"version": 1, "items": []}


def write_index(index: dict) -> None:
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    index["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    INDEX_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def select_hero_image(categories_primary: list[str], categories_secondary: list[str]) -> str:
    for cat in (categories_primary or []) + (categories_secondary or []):
        if not cat:
            continue
        if cat in CATEGORY_HERO:
            return CATEGORY_HERO[cat]
        # 부분 일치 (예: "발효" → fallback)
        for key, path in CATEGORY_HERO.items():
            if key in cat:
                return path
    return DEFAULT_HERO


def extract_pdf_figures(pdf_url: str, out_dir: Path, max_images: int = 6) -> list[dict]:
    """PDF 에서 그림을 추출 → PNG. 첫 max_images 개만 사용.
    PyMuPDF 가 없거나 PDF 가 받아지지 않으면 빈 리스트.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        err("PyMuPDF 미설치 — figure 추출 생략")
        return []

    try:
        r = requests.get(pdf_url, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        err(f"PDF 다운로드 실패: {e}")
        return []

    pdf_bytes = r.content
    out_dir.mkdir(parents=True, exist_ok=True)
    figures: list[dict] = []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        err(f"PDF 열기 실패: {e}")
        return []

    try:
        seen_hashes: set[int] = set()
        idx = 0
        for page in doc:
            for img in page.get_images(full=True):
                if idx >= max_images:
                    break
                xref = img[0]
                try:
                    base = doc.extract_image(xref)
                except Exception:
                    continue
                image_bytes = base.get("image")
                if not image_bytes:
                    continue
                h = hash(image_bytes)
                if h in seen_hashes:
                    continue
                # 너무 작은 이미지 (로고/장식) 제외
                if len(image_bytes) < 8 * 1024:
                    continue
                seen_hashes.add(h)
                ext = base.get("ext", "png")
                # PNG 통일은 비용이라 원본 확장자 유지 + 단순 변환은 생략
                fname = f"pdf-fig-{idx + 1}.{ext}"
                (out_dir / fname).write_bytes(image_bytes)
                rel = f"/static/img/insights/articles/{out_dir.name}/{fname}"
                figures.append({"src": rel, "caption": ""})
                idx += 1
            if idx >= max_images:
                break
    finally:
        doc.close()

    return figures


def split_paragraphs(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def render_html(payload: dict, env: Environment) -> str:
    tpl = env.get_template("insight_template.html.j2")
    categories_primary = payload.get("categories_primary") or []
    categories_secondary = payload.get("categories_secondary") or []
    all_cats = " · ".join([c for c in categories_primary + categories_secondary if c])

    summary_paragraphs = split_paragraphs(payload.get("summary") or "")
    implications = payload.get("implications") or {}
    if not isinstance(implications, dict):
        implications = {}
    # 사람이 읽기 좋은 라벨 정규화
    label_map = {
        "농가/가공장": "농가 · 가공장",
        "로스터/큐그레이더": "로스터 · 큐그레이더",
    }
    implications_norm = {label_map.get(k, k): v for k, v in implications.items() if v}

    date_display = ""
    if payload.get("date"):
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", payload["date"])
        if m:
            date_display = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"

    data_charts = payload.get("data_charts") or []

    return tpl.render(
        title_ko=payload.get("title_ko", ""),
        title_original=payload.get("title_original", ""),
        authors=payload.get("authors", ""),
        one_liner=payload.get("one_liner", ""),
        date_display=date_display,
        journal=payload.get("journal", ""),
        pub_date=payload.get("pub_date", ""),
        doi=payload.get("doi", ""),
        all_categories=all_cats,
        hero_image=payload.get("hero_image") or DEFAULT_HERO,
        summary_paragraphs=summary_paragraphs,
        key_findings=payload.get("key_findings") or [],
        methodology=payload.get("methodology", ""),
        implications=implications_norm,
        limitations=payload.get("limitations", ""),
        glossary=payload.get("glossary") or [],
        citation_apa=payload.get("citation_apa", ""),
        links=payload.get("links") or {},
        source_basis=payload.get("source_basis", "abstract_only"),
        data_charts=data_charts,
        data_charts_json=json.dumps(data_charts, ensure_ascii=False),
        figures=payload.get("figures") or [],
        # easy_* 필드 — 사이드카 JSON 이 친근 본문을 제공하면 우선 사용. 없으면 템플릿이 폴백.
        easy_hero_emoji=payload.get("easy_hero_emoji") or "",
        easy_hero_title=payload.get("easy_hero_title") or "",
        easy_intro_paragraphs=payload.get("easy_intro_paragraphs") or [],
        easy_concepts=payload.get("easy_concepts") or [],
        easy_findings=payload.get("easy_findings") or [],
        easy_tables=payload.get("easy_tables") or [],
        easy_summary=payload.get("easy_summary") or "",
    )


def process_one(payload: dict, env: Environment) -> dict | None:
    """단일 인사이트 처리. index 에 추가될 요약 객체 반환 (실패 시 None)."""
    payload_id = payload.get("id")
    if not payload_id:
        err("payload.id 없음 — 건너뜀")
        return None
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9\-]+$", payload_id):
        err(f"잘못된 id: {payload_id}")
        return None

    # hero image 결정 (payload 가 지정 안 했으면 카테고리로 추론)
    if not payload.get("hero_image"):
        payload["hero_image"] = select_hero_image(
            payload.get("categories_primary") or [],
            payload.get("categories_secondary") or [],
        )

    # PDF figure 추출 (OA fulltext 인 경우만)
    pdf_url = (payload.get("links") or {}).get("oa_pdf")
    if pdf_url and payload.get("source_basis") == "fulltext":
        fig_dir = FIGURES_ROOT / payload_id
        figures = extract_pdf_figures(pdf_url, fig_dir)
        if figures:
            existing = payload.get("figures") or []
            payload["figures"] = existing + figures
            log(f"  추출된 figure {len(figures)}개")

    # HTML 렌더
    html = render_html(payload, env)

    # 저장
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = INSIGHTS_DIR / f"{payload_id}.json"
    html_path = INSIGHTS_DIR / f"{payload_id}.html"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html_path.write_text(html, encoding="utf-8")
    log(f"  저장: {json_path.name}, {html_path.name}")

    # index 요약 객체
    return {
        "id": payload_id,
        "date": payload.get("date"),
        "title_ko": payload.get("title_ko"),
        "one_liner": payload.get("one_liner"),
        "categories_primary": payload.get("categories_primary") or [],
        "categories_secondary": payload.get("categories_secondary") or [],
        "hero_image": payload["hero_image"],
        "journal": payload.get("journal"),
        "pub_date": payload.get("pub_date"),
        "source_basis": payload.get("source_basis"),
    }


def main() -> int:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
    if not (client_id and client_secret and refresh_token):
        err("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN 미설정")
        return 2

    try:
        access_token = get_access_token(client_id, client_secret, refresh_token)
    except Exception as e:
        err(f"access token 획득 실패: {e}")
        return 3

    try:
        candidates = drive_search_files(access_token)
    except Exception as e:
        err(f"Drive 검색 실패: {e}")
        return 4

    log(f"Drive 후보 파일: {len(candidates)}개")

    index = read_index()
    known_ids = {it.get("id") for it in (index.get("items") or [])}
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        keep_trailing_newline=False,
    )
    # 템플릿이 |e 를 명시적으로 호출 → autoescape 비활성

    new_count = 0
    for meta in candidates:
        try:
            text = drive_download_text(meta, access_token)
        except Exception as e:
            err(f"{meta['name']} 다운로드 실패: {e}")
            continue

        # JSON 추출 — 본문이 JSON 단일 객체로 가정
        text = text.strip()
        # Google Doc 으로 export 시 앞쪽에 줄바꿈/제목이 붙는 경우 첫 `{` 부터 잘라냄
        first_brace = text.find("{")
        if first_brace < 0:
            err(f"{meta['name']} 에 JSON 객체 없음 — 건너뜀")
            continue
        try:
            payload = json.loads(text[first_brace:])
        except ValueError as e:
            err(f"{meta['name']} JSON 파싱 실패: {e}")
            continue

        payload_id = payload.get("id")
        if not payload_id or payload_id in known_ids:
            continue

        log(f"신규 인사이트: {payload_id}")
        summary = process_one(payload, env)
        if summary:
            items = index.setdefault("items", [])
            items.append(summary)
            known_ids.add(payload_id)
            new_count += 1

    if new_count == 0:
        log("새 인사이트 없음 — index 갱신 안 함")
        return 0

    # 최신순 정렬
    index["items"].sort(
        key=lambda x: (x.get("date") or "", x.get("id") or ""), reverse=True,
    )
    write_index(index)
    log(f"신규 {new_count}건 반영 — index 갱신 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
