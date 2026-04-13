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
from datetime import datetime
from typing import Optional

DB_PATH = os.environ.get(
    "COFFEE_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "coffee.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS coffees (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    roastery   TEXT,
    roast_date TEXT,
    process    TEXT,
    status     TEXT,
    cup_notes  TEXT,
    comment    TEXT,
    serve_date TEXT,
    notion_id  TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_coffees_roast_date ON coffees(roast_date DESC);
CREATE INDEX IF NOT EXISTS idx_coffees_status ON coffees(status);
CREATE INDEX IF NOT EXISTS idx_coffees_name ON coffees(name);
"""


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
    }


def list_all() -> list:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM coffees ORDER BY "
            "CASE WHEN status='예정' THEN 0 ELSE 1 END, "
            "roast_date DESC, id DESC"
        ).fetchall()
    return [_row_to_api(r) for r in rows]


def list_today_and_history():
    """현재 '진행 중' 항목과 최근 30일 히스토리를 한글 키로 반환."""
    from datetime import timedelta

    today = []
    history = []
    one_month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    with connect() as conn:
        rows = conn.execute("SELECT * FROM coffees").fetchall()

    items = [_row_to_api(r) for r in rows]

    def sort_key(item):
        status = item.get("상태")
        status_priority = 0 if status == "예정" else 1
        roast = item.get("로스팅") or {}
        start = roast.get("start") or ""
        return (status_priority, -_date_to_ts(start))

    for item in items:
        if not item.get("커피"):
            continue
        roast = item.get("로스팅") or {}
        roast_start = roast.get("start")
        if roast_start is None or roast_start >= one_month_ago:
            history.append(item)
        if item.get("상태") == "진행 중":
            today.append(item)

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
