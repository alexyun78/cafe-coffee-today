# -*- coding: utf-8 -*-
"""주변 가게 네이버 리뷰 수집 → Cloudflare Worker(D1) 인제스트 어댑터.

GitHub Actions(nearby-collect.yml)에서 실행. 파싱·예의 규칙은
collect_nearby.py 의 함수를 그대로 재사용하고, 저장만 로컬 SQLite 대신
Worker 의 POST /api/nearby/ingest 로 보낸다.

환경변수:
  WORKER_BASE  : Worker 베이스 URL (기본 https://cafe-coffee.92cafe.workers.dev)
  ADMIN_PIN    : /api/admin/verify 로 토큰 발급 (GH Secret)
  NAVER_CLIENT_ID / NAVER_CLIENT_SECRET : 블로그 검색 API (선택, GH Secret)
"""
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_nearby as cn  # noqa: E402 — 파싱 함수 재사용 (db 는 호출하지 않음)

KST = timezone(timedelta(hours=9))
WORKER_BASE = os.environ.get("WORKER_BASE", "https://cafe-coffee.92cafe.workers.dev").rstrip("/")
ADMIN_PIN = os.environ.get("ADMIN_PIN", "").strip()
TIMEOUT = 20


def api(session, method, path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = session.request(method, WORKER_BASE + path, headers=headers,
                        json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def main() -> int:
    if not ADMIN_PIN:
        print("ERROR: ADMIN_PIN 환경변수 필요", file=sys.stderr)
        return 2
    s = requests.Session()
    started_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    tok = api(s, "POST", "/api/admin/verify", body={"pin": ADMIN_PIN}).get("token")
    if not tok:
        print("ERROR: 관리자 토큰 발급 실패", file=sys.stderr)
        return 2

    shops = api(s, "GET", "/api/nearby/collect-targets", token=tok).get("shops", [])
    if not shops:
        api(s, "POST", "/api/nearby/ingest", token=tok,
            body={"run": {"started_at": started_at, "ok": True,
                          "message": "수집 대상 없음 (place_id 등록된 가게 0곳)"}})
        return 0

    today_kst = datetime.now(KST).date().isoformat()
    naver = requests.Session()
    counts, reviews, keywords = [], [], []
    done, new_candidates, errors = 0, 0, []

    for i, shop in enumerate(shops):
        if i:
            time.sleep(3 + random.uniform(0, 2))  # 가게당 3~5초 — 예의 유지
        try:
            vt, bt, score, kws, revs, status = cn.fetch_shop(naver, shop["place_id"])
        except requests.RequestException as e:
            errors.append(f"{shop['name']}: {str(e)[:60]}")
            continue
        if status == 429:
            errors.append(f"{shop['name']}: 429 rate-limit — 전체 중단")
            break
        if status != 200:
            errors.append(f"{shop['name']}: HTTP {status}")
            continue
        if vt is not None or bt is not None:
            counts.append({"shop_id": shop["id"], "fetched_date": today_kst,
                           "visitor_count": vt, "blog_count": bt, "visitor_score": score})
        if kws:
            keywords.append({"shop_id": shop["id"],
                             "keywords_json": json.dumps(kws, ensure_ascii=False)})
        blog_posts = cn.fetch_blog_posts(naver, shop["name"])
        for rv in revs + blog_posts:
            reviews.append({
                "shop_id": shop["id"], "source": rv["source"],
                "visited_date": rv["visited"], "body": rv["body"],
                "author": rv["author"], "url": rv.get("url"),
                "review_hash": cn.review_hash(shop["id"], rv),
            })
            new_candidates += 1
        done += 1
        print(f"  {shop['name']:<22} 방문자 {vt} (★{score}) · 블로그 {bt} · "
              f"표본 {len(revs)}건 · 블로그검색 {len(blog_posts)}건")

    msg = f"{len(shops)}곳 중 {done}곳 수집, 표본 후보 {new_candidates}건 [GH Actions]"
    if not (cn.NAVER_CLIENT_ID and cn.NAVER_CLIENT_SECRET):
        msg += " (블로그 검색 생략 — NAVER API 키 없음)"
    if errors:
        msg += f" / 오류 {len(errors)}건: " + "; ".join(errors[:5])
    ok = done > 0

    res = api(s, "POST", "/api/nearby/ingest", token=tok, body={
        "run": {"started_at": started_at, "ok": ok, "message": msg},
        "counts": counts, "reviews": reviews, "keywords": keywords,
    })
    print(f"ingest 적용 {res.get('applied')}문 | {msg}")
    # 수집 0곳이면 실패로 처리해 Actions 로그에서 눈에 띄게
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
