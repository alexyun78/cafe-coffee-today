# -*- coding: utf-8 -*-
"""주변 가게 네이버 리뷰 수집기 (requests-only, anti-bot 우회 없음).

수집 범위 — 정직하게 가능한 것만:
  1. 방문자/블로그 리뷰 "총 건수"  : 페이지에 그대로 실리는 정확한 값 → 일별 스냅샷
  2. 방문자 리뷰 "최근 ~10건 표본" : 첫 페이지 로드(SSR __APOLLO_STATE__)에 실리는
     분량만. 더보기/GraphQL 페이지네이션은 anti-bot 보호 대상이라 시도하지 않는다.

대상: nearby_shops 중 place_id 가 있는 가게.
예의: 가게당 3~5초 간격, 429 응답 시 즉시 전체 중단.

실행:
  python scripts/collect_nearby.py            # 전체 수집
  python scripts/collect_nearby.py --dry 1939889314   # place id 1곳만 파싱 테스트(저장 안 함)
"""
import hashlib
import json
import random
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402

KST = timezone(timedelta(hours=9))
UA = ("Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
TIMEOUT = 15

RE_VISITOR_TOTAL = re.compile(r'"visitorReviewsTotal"\s*:\s*(\d+)')
RE_BLOG_TOTAL = re.compile(r'"cafeBlogReviewsTotal"\s*:\s*(\d+)')
RE_VISITOR_SCORE = re.compile(r'"visitorReviewsScore"\s*:\s*([\d.]+)')
RE_VISITOR_TEXT = re.compile(r"방문자\s*리?뷰\s*([\d,]+)")
RE_BLOG_TEXT = re.compile(r"블로그\s*리?뷰\s*([\d,]+)")

RE_DATE_FULL = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
RE_DATE_YY = re.compile(r"\b(\d{2})\.(\d{1,2})\.(\d{1,2})\b")
RE_DATE_MD = re.compile(r"\b(\d{1,2})\.(\d{1,2})\b")


def parse_visited(raw, today: date):
    """네이버 visited 표기('5.31.토', '24.12.30.월', '2025년 12월 3일')를 ISO 날짜로."""
    if not raw:
        return None
    s = str(raw)
    m = RE_DATE_FULL.search(s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = RE_DATE_YY.search(s)
        if m:
            yy, mo, d = map(int, m.groups())
            y = 2000 + yy
            if mo > 12:  # 'YY.M.D'가 아니라 'M.D.x' 오매칭인 경우 방어
                return None
        else:
            m = RE_DATE_MD.search(s)
            if not m:
                return None
            mo, d = map(int, m.groups())
            y = today.year
    try:
        dt_ = date(y, mo, d)
    except ValueError:
        return None
    if dt_ > today:  # 연도 없는 표기가 미래로 계산되면 작년
        try:
            dt_ = date(y - 1, mo, d)
        except ValueError:
            return None
    return dt_.isoformat()


def extract_apollo(html: str):
    """window.__APOLLO_STATE__ = {...} 를 raw_decode 로 안전하게 파싱."""
    idx = html.find("__APOLLO_STATE__")
    if idx < 0:
        return None
    brace = html.find("{", idx)
    if brace < 0:
        return None
    try:
        state, _ = json.JSONDecoder().raw_decode(html, brace)
        return state if isinstance(state, dict) else None
    except (ValueError, json.JSONDecodeError):
        return None


def _resolve_author(state: dict, review: dict):
    a = review.get("author")
    if isinstance(a, dict):
        ref = a.get("__ref")
        if ref and ref in state:
            a = state[ref]
        nick = a.get("nickname") or a.get("name")
        if nick:
            return str(nick)
    return None


def extract_reviews(state: dict, today: date) -> list:
    """APOLLO state 에서 리뷰 객체를 방어적으로 추출.
    VisitorReview = 방문자 리뷰, FsasReview(type=blog) = 페이지에 같이 실리는 블로그 리뷰."""
    out = []
    for key, v in state.items():
        if not isinstance(v, dict):
            continue
        tn = v.get("__typename") or ""
        # VisitorReview / FsasReview 본문 객체만 (Stats·Theme·Author 류 제외)
        if not tn.endswith("Review"):
            continue
        body = v.get("body") or v.get("contents") or v.get("content")
        if not isinstance(body, str) or not body.strip():
            continue
        is_blog = tn == "FsasReview" or v.get("type") == "blog"
        visited_raw = (v.get("visited") or v.get("visitedDate")
                       or v.get("date") or v.get("created"))
        author = _resolve_author(state, v)
        if is_blog and not author:
            nm = v.get("name")          # FsasReview 는 블로그 이름이 name 필드
            author = str(nm) if nm else None
        out.append({
            "rid": str(v.get("id") or key),
            "source": "blog" if is_blog else "visitor",
            "body": body.strip(),
            "visited_raw": visited_raw,
            "visited": parse_visited(visited_raw, today),
            "author": author,
        })
    return out


def fetch_shop(session, place_id: str):
    """리뷰 페이지 1회 GET → (visitor_total, blog_total, score, reviews, status_code)."""
    url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?reviewSort=recent"
    r = session.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    if r.status_code != 200:
        return None, None, None, [], r.status_code
    # 네이버가 Content-Type 에 charset 을 안 실어주면 requests 가 ISO-8859-1 로
    # 잘못 디코딩해 한글이 깨진다 (mojibake 가 DB 까지 저장됐던 원인). UTF-8 강제.
    r.encoding = "utf-8"
    html = r.text
    today = datetime.now(KST).date()

    def _first_int(*patterns):
        for p in patterns:
            m = p.search(html)
            if m:
                return int(m.group(1).replace(",", ""))
        return None

    visitor_total = _first_int(RE_VISITOR_TOTAL, RE_VISITOR_TEXT)
    blog_total = _first_int(RE_BLOG_TOTAL, RE_BLOG_TEXT)
    m = RE_VISITOR_SCORE.search(html)
    score = float(m.group(1)) if m else None

    reviews = []
    state = extract_apollo(html)
    if state:
        reviews = extract_reviews(state, today)
    return visitor_total, blog_total, score, reviews, 200


def review_hash(shop_id: int, rv: dict) -> str:
    # 네이버 리뷰 id 가 있으면 그것 기준 (가장 안정적), 없으면 본문+작성자+방문일
    if rv.get("rid"):
        basis = f"naver|{rv['rid']}"
    else:
        basis = f"{shop_id}|naver|{rv.get('author')}|{rv.get('visited_raw')}|{rv['body']}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def collect_all() -> str:
    """전체 수집. 요약 메시지 반환 (실패 시 예외 대신 메시지에 기록)."""
    shops = db.nearby_shops_for_collect()
    if not shops:
        return "수집 대상 없음 (place_id 등록된 가게 0곳)"
    today_kst = datetime.now(KST).date().isoformat()
    session = requests.Session()
    done, new_reviews, errors = 0, 0, []
    for i, s in enumerate(shops):
        if i:
            time.sleep(3 + random.uniform(0, 2))   # 가게당 3~5초 — 예의 유지
        try:
            vt, bt, score, revs, status = fetch_shop(session, s["place_id"])
        except requests.RequestException as e:
            errors.append(f"{s['name']}: {str(e)[:60]}")
            continue
        if status == 429:
            errors.append(f"{s['name']}: 429 rate-limit — 전체 중단")
            break
        if status != 200:
            errors.append(f"{s['name']}: HTTP {status}")
            continue
        if vt is not None or bt is not None:
            db.nearby_record_counts(s["id"], today_kst, vt, bt, score)
        for rv in revs:
            if db.nearby_upsert_review(
                s["id"], rv["source"], rv["visited"], rv["body"],
                rv["author"], review_hash(s["id"], rv),
            ):
                new_reviews += 1
        done += 1
        print(f"  {s['name']:<22} 방문자 {vt} (★{score}) · 블로그 {bt} · 표본 {len(revs)}건")
    msg = f"{len(shops)}곳 중 {done}곳 수집, 신규 표본 리뷰 {new_reviews}건"
    if errors:
        msg += f" / 오류 {len(errors)}건: " + "; ".join(errors[:5])
    return msg


def run() -> str:
    """run 기록을 남기며 수집 (API 백그라운드 스레드와 CLI 공용 진입점)."""
    run_id = db.nearby_run_start()
    try:
        msg = collect_all()
        ok = "오류" not in msg or "수집" in msg
        db.nearby_run_finish(run_id, ok, msg)
        return msg
    except Exception as e:  # noqa: BLE001 — run 기록은 반드시 닫는다
        db.nearby_run_finish(run_id, False, f"예외: {str(e)[:200]}")
        raise


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--dry":
        pid = sys.argv[2]
        vt, bt, score, revs, status = fetch_shop(requests.Session(), pid)
        print(f"HTTP {status} · 방문자 {vt} (★{score}) · 블로그 {bt} · 표본 {len(revs)}건")
        for rv in revs[:15]:
            print(f"  [{rv['source']}] [{rv['visited']}] ({rv['author']}) {rv['body'][:70]}")
        return
    db.init_schema()
    print(run())


if __name__ == "__main__":
    main()
