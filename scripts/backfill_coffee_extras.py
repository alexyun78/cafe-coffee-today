"""coffee-export CSV → coffees 테이블의 신규 3개 컬럼 백필.

- 신규 컬럼: category(구분), brewed_at(BREWED AT), roast_point(로스팅 포인트)
- 매칭: name(커피) 완전 일치 — 같은 이름의 모든 행을 동일 값으로 일괄 갱신
- 멱등: 이미 채워진 행도 동일 값으로 덮어씀 (안전)
"""
import csv
import os
import sys

# 프로젝트 루트를 import path에 추가
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db


def to_int(v):
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def main(csv_path: str):
    db.init_schema()  # 신규 컬럼 ALTER 보장

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("커피") or "").strip()
            if not name:
                continue
            rows.append({
                "name": name,
                "category": (row.get("구분") or "").strip() or None,
                "brewed_at": to_int(row.get("BREWED AT")),
                "roast_point": to_int(
                    row.get("로스팅 포인트(LIGHT:30 MEDIUM 60 DARK 80)")
                    or row.get("로스팅 포인트")
                ),
            })

    matched_names = 0
    updated_rows = 0
    unmatched = []
    with db.connect() as conn:
        for r in rows:
            cur = conn.execute(
                """UPDATE coffees
                       SET category=?, brewed_at=?, roast_point=?,
                           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                     WHERE name=?""",
                (r["category"], r["brewed_at"], r["roast_point"], r["name"]),
            )
            if cur.rowcount > 0:
                matched_names += 1
                updated_rows += cur.rowcount
            else:
                unmatched.append(r["name"])

    print(f"CSV 행: {len(rows)}건")
    print(f"매칭된 커피 이름: {matched_names}건")
    print(f"갱신된 DB 행: {updated_rows}건")
    if unmatched:
        print("매칭 실패:")
        for n in unmatched:
            print(f"  - {n}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "coffee-export-20260426.csv")
    main(path)
