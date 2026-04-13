"""Notion → SQLite 일회성 마이그레이션 스크립트.

사용법:
    python migrate_notion.py

환경 변수 (.env):
    NOTION_TOKEN, DATABASE_ID

멱등성: notion_id 기준 UPSERT. 여러 번 실행해도 안전.
"""
import os
import sys

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    print("❌ NOTION_TOKEN 또는 DATABASE_ID가 .env에 없습니다.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def query_all(db_id: str) -> list:
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {"page_size": 100}
    results = []
    while True:
        res = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return results


def humanize_property(prop: dict):
    t = prop.get("type")
    if not t:
        return None
    if t == "title":
        return "".join(r.get("plain_text", "") for r in prop["title"]).strip() or None
    if t == "rich_text":
        return "".join(r.get("plain_text", "") for r in prop["rich_text"]).strip() or None
    if t == "number":
        return prop["number"]
    if t == "select":
        return prop["select"]["name"] if prop["select"] else None
    if t == "multi_select":
        return ", ".join(o["name"] for o in prop["multi_select"])
    if t == "status":
        return prop["status"]["name"] if prop["status"] else None
    if t == "date":
        if not prop["date"]:
            return None
        return prop["date"].get("start")
    return None


def flatten_row(page: dict) -> dict:
    out = {}
    for name, prop in page.get("properties", {}).items():
        out[name] = humanize_property(prop)
    return out


def main():
    db.init_schema()
    print(f"[migrate] Notion DB 조회 중... ({DATABASE_ID})")
    pages = query_all(DATABASE_ID)
    print(f"[migrate]   총 {len(pages)}개 페이지 로드")

    inserted = 0
    updated = 0
    skipped = 0

    for pg in pages:
        row = flatten_row(pg)
        name = row.get("커피")
        if not name:
            skipped += 1
            continue

        data = {
            "name": name,
            "roastery": row.get("로스터리"),
            "roast_date": row.get("로스팅"),
            "process": row.get("프로세싱"),
            "status": row.get("상태"),
            "cup_notes": row.get("컵노트"),
            "comment": row.get("감상"),
            "serve_date": row.get("제공일"),
            "notion_id": pg.get("id"),
        }
        result = db.upsert_from_notion(data)
        if result == "inserted":
            inserted += 1
        else:
            updated += 1

    print("-" * 40)
    print(f"[migrate] 이전 완료")
    print(f"[migrate]   신규 INSERT: {inserted}건")
    print(f"[migrate]   기존 UPDATE: {updated}건")
    print(f"[migrate]   건너뜀(이름 없음): {skipped}건")
    print(f"[migrate]   DB 파일: {db.DB_PATH}")


if __name__ == "__main__":
    main()
