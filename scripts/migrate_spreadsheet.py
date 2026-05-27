"""스프레드시트 데이터 → DB 마이그레이션.

Google Drive MCP 에서 내보낸 파일을 파싱하여
suppliers, green_beans, purchases, roasting_logs 테이블에 적재.

Usage:
    python scripts/migrate_spreadsheet.py [export_file_path]

export_file_path 를 생략하면 기본 경로에서 읽음.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

DEFAULT_EXPORT = os.path.join(
    os.path.expanduser("~"),
    ".claude", "projects", "D--python-92-cafe-today-coffee",
    "feeb080c-5ae4-40e1-8fed-ec0b444a824b", "tool-results",
    "mcp-claude_ai_Google_Drive-read_file_content-1779889746473.txt",
)

SUPPLIER_MAP = {
    "레햄코리아": "레햄",
    "커피리브레": "리브레",
    "소펙스코리아": "소펙",
    "커만사": "커만사",
    "커피플랜트": "커플",
    "알마씨엘로": "알마",
    "더드립": "더드립",
}


def load_content(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fileContent", "")


def parse_cells(line: str) -> list:
    cells = line.split("|")
    cells = [c.strip() for c in cells]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def clean_name(raw: str) -> tuple:
    raw = raw.replace("\\[", "[").replace("\\]", "]").strip()
    m = re.match(r"^\[([^\]]+)\]\s*(.+)$", raw)
    if m:
        prefix = m.group(1).strip()
        name = m.group(2).strip()
    else:
        prefix = ""
        name = raw
    cup_match = re.search(r"\(([^)]+)\)$", name)
    cup_notes = cup_match.group(1).strip() if cup_match else ""
    if cup_match:
        name = name[: cup_match.start()].strip()
    return prefix, name, cup_notes


def parse_date(d: str) -> str:
    d = d.replace("\\.", ".").strip()
    m = re.match(r"(\d{4})\.\s*(\d{2})\.\s*(\d{2})", d)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return d


def parse_number(s: str) -> float:
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0


def ensure_supplier(name: str) -> int:
    short = SUPPLIER_MAP.get(name, name)
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM suppliers WHERE name=?", (name,)).fetchone()
        if row:
            return row["id"]
    return db.create_supplier({"name": name, "short_name": short})


def ensure_green_bean(name: str, supplier_id: int, process: str,
                      grade: str = "", cup_notes: str = "",
                      is_decaf: int = 0) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM green_beans WHERE name=? AND supplier_id=? AND process=?",
            (name, supplier_id, process),
        ).fetchone()
        if row:
            if cup_notes:
                conn.execute(
                    "UPDATE green_beans SET cup_notes=? WHERE id=? AND (cup_notes IS NULL OR cup_notes='')",
                    (cup_notes, row["id"]),
                )
            return row["id"]
    return db.create_green_bean({
        "name": name,
        "supplier_id": supplier_id,
        "process": process,
        "grade": grade,
        "cup_notes": cup_notes,
        "is_decaf": is_decaf,
    })


def migrate_purchases(lines: list):
    count = 0
    for i in range(306, min(len(lines), 380)):
        line = lines[i].strip()
        if not line or "| :-:" in line:
            continue
        cells = parse_cells(line)
        if len(cells) < 9:
            continue
        date_str = cells[0]
        if not re.search(r"\d{4}", date_str):
            continue
        date = parse_date(date_str)
        raw_name = cells[1]
        supplier_name = cells[2].strip()
        process = cells[3].strip()
        grade = cells[4].strip()
        unit_price = int(parse_number(cells[5]))
        qty = parse_number(cells[6])
        discount_raw = parse_number(cells[7])
        total_raw = int(parse_number(cells[8]))

        if not supplier_name or not raw_name or qty == 0:
            continue

        prefix, bean_name, cup_notes = clean_name(raw_name)
        is_decaf = 1 if "디카페인" in process or "디카페인" in bean_name else 0
        sid = ensure_supplier(supplier_name)
        gbid = ensure_green_bean(bean_name, sid, process, grade, cup_notes, is_decaf)

        computed_total = int(qty * unit_price)
        discount = computed_total - total_raw if total_raw < computed_total else 0

        db.create_purchase({
            "green_bean_id": gbid,
            "purchase_date": date,
            "quantity_kg": qty,
            "unit_price": unit_price,
            "discount": discount,
        })
        count += 1
    print(f"  구매 기록: {count}건 이전")
    return count


def migrate_roasting(lines: list):
    count = 0
    for i in range(2, 210):
        line = lines[i].strip()
        if not line or "| :-:" in line:
            continue
        cells = parse_cells(line)
        if len(cells) < 11:
            continue
        date_str = cells[0]
        if not re.search(r"\d{4}", date_str):
            continue
        date = parse_date(date_str)
        raw_name = cells[1]
        supplier_name = cells[2].strip()
        process = cells[3].strip()
        grade = cells[4].strip()
        unit_price = int(parse_number(cells[5]))
        loss_pct = parse_number(cells[8])
        input_g = parse_number(cells[9])
        output_g = parse_number(cells[10])

        if not supplier_name or not raw_name or input_g == 0:
            continue

        prefix, bean_name, cup_notes = clean_name(raw_name)
        is_decaf = 1 if "디카페인" in process or "디카페인" in bean_name else 0
        sid = ensure_supplier(supplier_name)
        gbid = ensure_green_bean(bean_name, sid, process, grade, cup_notes, is_decaf)

        db.create_roasting_log({
            "green_bean_id": gbid,
            "roast_date": date,
            "input_weight_g": input_g,
            "output_weight_g": output_g if output_g > 0 else None,
        })
        count += 1
    print(f"  로스팅 기록: {count}건 이전")
    return count


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXPORT
    if not os.path.exists(path):
        print(f"파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    print(f"소스: {path}")
    content = load_content(path)
    lines = content.split("\n")
    print(f"총 {len(lines)}줄 파싱")

    db.init_schema()

    with db.connect() as conn:
        existing = conn.execute("SELECT COUNT(*) AS c FROM purchases").fetchone()["c"]
        if existing > 0:
            print(f"이미 {existing}건의 구매 기록이 있습니다. 중복 방지를 위해 건너뜁니다.")
            print("초기화하려면 purchases, roasting_logs 테이블을 비우고 다시 실행하세요.")
            return

    print("\n구매 기록 이전 중...")
    p_count = migrate_purchases(lines)

    print("\n로스팅 기록 이전 중...")
    r_count = migrate_roasting(lines)

    print("\n재고 확인:")
    inv = db.inventory_list()
    for item in inv:
        remaining = item["remaining_kg"]
        name = item["name"]
        short = item.get("supplier_short") or ""
        label = f"[{short}] {name}" if short else name
        status = "✅" if remaining > 5 else "⚠️" if remaining > 0 else "❌"
        print(f"  {status} {label}: {remaining:.1f}kg (구매 {item['purchased_kg']:.1f}kg - 사용 {item['used_kg']:.1f}kg)")

    print(f"\n완료: 공급업체 {len(db.list_suppliers())}곳, "
          f"생두 {len(db.list_green_beans(True))}종, "
          f"구매 {p_count}건, 로스팅 {r_count}건")


if __name__ == "__main__":
    main()
