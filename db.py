"""SQLite wrapper for cafe-today-coffee.

스키마:
    coffees(id, name, roastery, roast_date, process, status,
            cup_notes, comment, serve_date, notion_id, created_at, updated_at)

API 응답은 기존 Notion 스키마와 호환되도록 한글 키(`커피`, `로스팅` 등)로
변환되어 리턴된다. 날짜 필드는 {"start": "YYYY-MM-DD", "end": None} 객체 형태.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional

DB_PATH = os.environ.get(
    "COFFEE_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "coffee.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS coffees (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    roastery     TEXT,
    roast_date   TEXT,
    process      TEXT,
    status       TEXT,
    cup_notes    TEXT,
    comment      TEXT,
    serve_date   TEXT,
    category     TEXT,
    brewed_at    INTEGER,
    roast_point  INTEGER,
    availability TEXT DEFAULT '운영',
    notion_id    TEXT UNIQUE,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_coffees_roast_date ON coffees(roast_date DESC);
CREATE INDEX IF NOT EXISTS idx_coffees_status ON coffees(status);
CREATE INDEX IF NOT EXISTS idx_coffees_name ON coffees(name);
"""

_EXTRA_COLUMNS = (
    ("category", "TEXT"),
    ("brewed_at", "INTEGER"),
    ("roast_point", "INTEGER"),
    ("availability", "TEXT DEFAULT '운영'"),
)


def _ensure_dir():
    d = os.path.dirname(DB_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


@contextmanager
def connect():
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def init_schema():
    with connect() as conn:
        conn.executescript(SCHEMA)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(coffees)").fetchall()}
        for col, ctype in _EXTRA_COLUMNS:
            if col not in existing:
                conn.execute(f"ALTER TABLE coffees ADD COLUMN {col} {ctype}")
        conn.execute(
            "UPDATE coffees SET availability='운영' WHERE availability IS NULL OR availability=''"
        )
        # 일회성 마이그레이션 기록 테이블
        conn.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY)")
        # 모든 행의 로스터리를 '92도씨 로스터리'로 통일 (1회만 실행)
        if not conn.execute(
            "SELECT 1 FROM migrations WHERE name=?", ("roastery_92cafe_default",)
        ).fetchone():
            conn.execute("UPDATE coffees SET roastery='92도씨 로스터리'")
            conn.execute(
                "INSERT INTO migrations (name) VALUES (?)", ("roastery_92cafe_default",)
            )


def _date_obj(s: Optional[str]):
    """Return Notion-compatible date object or None."""
    if not s:
        return None
    return {"start": s, "end": None}


def _row_to_api(row: sqlite3.Row) -> dict:
    """Convert DB row to API response (Korean keys, Notion-compatible shape)."""
    return {
        "id": row["id"],
        "커피": row["name"],
        "로스터리": row["roastery"],
        "로스팅": _date_obj(row["roast_date"]),
        "프로세싱": row["process"],
        "상태": row["status"],
        "컵노트": row["cup_notes"],
        "감상": row["comment"],
        "제공일": _date_obj(row["serve_date"]),
        "구분": row["category"],
        "BREWED AT": row["brewed_at"],
        "로스팅 포인트": row["roast_point"],
        "운영상태": row["availability"] or "운영",
    }


def list_all() -> list:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM coffees ORDER BY "
            "CASE WHEN status='예정' THEN 0 ELSE 1 END, "
            "roast_date DESC, id DESC"
        ).fetchall()
    return [_row_to_api(r) for r in rows]


def _months_ago_iso(months: int) -> str:
    """오늘 기준 N개월 전 날짜를 'YYYY-MM-DD'로 반환 (월말 일자는 안전하게 보정)."""
    t = date.today()
    m = t.month - months
    y = t.year
    while m < 1:
        m += 12
        y -= 1
    # 2/30 같은 무효 날짜 방지: 해당 월의 마지막 날로 클램프
    for d in (t.day, 28, 27, 26, 25):
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            continue
    return date(y, m, 1).isoformat()


def list_today_and_history():
    """현재 '진행 중' 항목과 히스토리(예정·완료만)를 한글 키로 반환.

    공개용: '완료' 항목은 최근 3개월 이내(제공일 우선, 없으면 로스팅일)만 노출.
    예정 항목은 향후 일정이므로 기간 필터 없이 모두 노출.

    히스토리 정렬:
      1) 예정 → 완료 순
      2) 예정: 로스팅 오래된 순(오름차순), 같은 날이면 가나다순
      3) 완료: 로스팅 최신순(내림차순), 같은 날이면 가나다순
    진행 중은 이미 '지금 제공 중'에 표시되므로 히스토리에서 제외.
    """
    today = []
    history = []
    cutoff = _months_ago_iso(3)

    with connect() as conn:
        rows = conn.execute("SELECT * FROM coffees").fetchall()

    items = [_row_to_api(r) for r in rows]

    for item in items:
        if not item.get("커피"):
            continue
        status = item.get("상태")
        if status == "진행 중":
            today.append(item)
        elif status == "예정":
            history.append(item)
        elif status == "완료":
            serve = (item.get("제공일") or {}).get("start") or ""
            roast = (item.get("로스팅") or {}).get("start") or ""
            ref = serve or roast
            if ref and ref >= cutoff:
                history.append(item)

    def sort_key(item):
        status = item.get("상태")
        status_priority = 0 if status == "예정" else 1
        roast = item.get("로스팅") or {}
        start = roast.get("start") or ""
        ts = _date_to_ts(start)
        name = item.get("커피") or ""
        if status == "예정":
            # 오래된 순 (오름차순)
            return (status_priority, ts, name)
        else:
            # 최신순 (내림차순)
            return (status_priority, -ts, name)

    history.sort(key=sort_key)
    return today, history


def _date_to_ts(s: str) -> float:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").timestamp()
    except Exception:
        return 0.0


def get_by_id(coffee_id: int) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM coffees WHERE id=?", (coffee_id,)).fetchone()
    return _row_to_api(row) if row else None


def create(data: dict) -> int:
    fields = (
        "name",
        "roastery",
        "roast_date",
        "process",
        "status",
        "cup_notes",
        "comment",
        "serve_date",
        "category",
        "brewed_at",
        "roast_point",
        "availability",
        "notion_id",
    )
    values = [data.get(f) for f in fields]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO coffees ({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
            values,
        )
        return cur.lastrowid


def update(coffee_id: int, data: dict) -> bool:
    allowed = (
        "name",
        "roastery",
        "roast_date",
        "process",
        "status",
        "cup_notes",
        "comment",
        "serve_date",
        "category",
        "brewed_at",
        "roast_point",
        "availability",
    )
    sets = [f"{k}=?" for k in allowed if k in data]
    if not sets:
        return False
    sets.append("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
    values = [data[k] for k in allowed if k in data] + [coffee_id]
    with connect() as conn:
        cur = conn.execute(
            f"UPDATE coffees SET {','.join(sets)} WHERE id=?", values
        )
        return cur.rowcount > 0


def set_availability_by_name(name: str, value: str) -> int:
    """같은 이름의 모든 원두에 운영/품절 상태를 일괄 적용."""
    if not name:
        return 0
    with connect() as conn:
        cur = conn.execute(
            "UPDATE coffees SET availability=?, "
            "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
            "WHERE name=?",
            (value, name),
        )
        return cur.rowcount


def complete_other_in_progress(except_id: Optional[int]) -> int:
    """'진행 중' 상태인 다른 커피를 '완료'로 변경. 변경된 행 수 반환."""
    with connect() as conn:
        if except_id is None:
            cur = conn.execute(
                "UPDATE coffees SET status='완료', "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                "WHERE status='진행 중'"
            )
        else:
            cur = conn.execute(
                "UPDATE coffees SET status='완료', "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                "WHERE status='진행 중' AND id<>?",
                (except_id,),
            )
        return cur.rowcount


def delete(coffee_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM coffees WHERE id=?", (coffee_id,))
        return cur.rowcount > 0


def upsert_from_notion(data: dict) -> str:
    """notion_id 기준 멱등 INSERT OR UPDATE. returns 'inserted' | 'updated'."""
    notion_id = data.get("notion_id")
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM coffees WHERE notion_id=?", (notion_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE coffees SET
                       name=?, roastery=?, roast_date=?, process=?, status=?,
                       cup_notes=?, comment=?, serve_date=?,
                       updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                   WHERE notion_id=?""",
                (
                    data.get("name"),
                    data.get("roastery"),
                    data.get("roast_date"),
                    data.get("process"),
                    data.get("status"),
                    data.get("cup_notes"),
                    data.get("comment"),
                    data.get("serve_date"),
                    notion_id,
                ),
            )
            return "updated"
        conn.execute(
            """INSERT INTO coffees
                   (name, roastery, roast_date, process, status,
                    cup_notes, comment, serve_date, notion_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                data.get("name"),
                data.get("roastery"),
                data.get("roast_date"),
                data.get("process"),
                data.get("status"),
                data.get("cup_notes"),
                data.get("comment"),
                data.get("serve_date"),
                notion_id,
            ),
        )
        return "inserted"


def suggestions() -> dict:
    """드롭다운용 DISTINCT 값, 최근 사용순."""
    def distinct(col: str, limit: int = 50) -> list:
        with connect() as conn:
            rows = conn.execute(
                f"SELECT {col} AS v, MAX(id) AS last_id FROM coffees "
                f"WHERE {col} IS NOT NULL AND {col} != '' "
                f"GROUP BY {col} ORDER BY last_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [r["v"] for r in rows]

    # cup_notes는 쉼표 구분 문자열 → 개별 맛으로 분리·중복 제거
    raw_notes = distinct("cup_notes", limit=200)
    seen = set()
    individual_notes = []
    for entry in raw_notes:
        for note in entry.split(","):
            note = note.strip()
            if note and note not in seen:
                seen.add(note)
                individual_notes.append(note)

    # 가장 최근 기록의 컵노트
    with connect() as conn:
        last_row = conn.execute(
            "SELECT cup_notes FROM coffees "
            "WHERE cup_notes IS NOT NULL AND cup_notes != '' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    last_cup_notes = last_row["cup_notes"] if last_row else ""

    return {
        "name": distinct("name"),
        "roastery": distinct("roastery"),
        "process": distinct("process"),
        "cup_notes": individual_notes,
        "last_cup_notes": last_cup_notes,
    }
