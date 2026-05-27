"""SQLite wrapper for cafe-today-coffee.

스키마:
    coffees(id, name, roastery, roast_date, process, status,
            cup_notes, comment, serve_date, notion_id, created_at, updated_at)
    suppliers(id, name, short_name, contact, notes)
    green_beans(id, name, supplier_id, origin_country, origin_region, process,
                grade, cup_notes, description, is_decaf, status)
    purchases(id, green_bean_id, purchase_date, quantity_kg, unit_price, ...)
    roasting_logs(id, green_bean_id, roast_date, input_weight_g, output_weight_g, ...)
    pricing(id, green_bean_id, weight_g, retail_price, wholesale_price)
    blends(id, name, description) + blend_components(blend_id, green_bean_id, ratio_pct)
    pin_attempts(ip, count, window_start, locked_until)

API 응답은 기존 Notion 스키마와 호환되도록 한글 키(`커피`, `로스팅` 등)로
변환되어 리턴된다. 날짜 필드는 {"start": "YYYY-MM-DD", "end": None} 객체 형태.
"""
import os
import sqlite3
import time
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

CREATE TABLE IF NOT EXISTS pin_attempts (
    ip            TEXT PRIMARY KEY,
    count         INTEGER NOT NULL DEFAULT 0,
    window_start  REAL NOT NULL,
    locked_until  REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS visits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,           -- ISO UTC
    date_kst    TEXT NOT NULL,           -- YYYY-MM-DD (KST)
    hour_kst    INTEGER NOT NULL,        -- 0..23 (KST)
    path        TEXT NOT NULL,
    visitor_id  TEXT NOT NULL,
    device      TEXT NOT NULL,           -- mobile|tablet|desktop
    is_new      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(date_kst);
CREATE INDEX IF NOT EXISTS idx_visits_visitor ON visits(visitor_id);

CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    coffee_id       INTEGER NOT NULL REFERENCES coffees(id) ON DELETE CASCADE,
    coffee_name     TEXT,                -- 제출 시점의 원두 이름 스냅샷 (재입고/복제 후에도 묶이도록)
    nickname        TEXT,
    rating          INTEGER NOT NULL,
    cup_notes_json  TEXT,                -- JSON array, 최대 3개
    comment         TEXT,
    ip_hash         TEXT,                -- SHA256(ip + FLASK_SECRET) — 동일성 비교용
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_coffee ON feedback(coffee_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_ip ON feedback(ip_hash, created_at);
"""

GREEN_BEAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    short_name  TEXT,
    contact     TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS green_beans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    supplier_id     INTEGER REFERENCES suppliers(id),
    origin_country  TEXT,
    origin_region   TEXT,
    process         TEXT NOT NULL,
    grade           TEXT,
    cup_notes       TEXT,
    description     TEXT,
    is_decaf        INTEGER DEFAULT 0,
    status          TEXT DEFAULT '활성',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(name, supplier_id, process)
);
CREATE INDEX IF NOT EXISTS idx_green_beans_name ON green_beans(name);
CREATE INDEX IF NOT EXISTS idx_green_beans_supplier ON green_beans(supplier_id);

CREATE TABLE IF NOT EXISTS purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    green_bean_id   INTEGER NOT NULL REFERENCES green_beans(id),
    purchase_date   TEXT NOT NULL,
    quantity_kg     REAL NOT NULL,
    unit_price      INTEGER NOT NULL,
    discount        INTEGER DEFAULT 0,
    total_price     INTEGER,
    lot_number      TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_purchases_bean ON purchases(green_bean_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date DESC);

CREATE TABLE IF NOT EXISTS roasting_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    green_bean_id     INTEGER NOT NULL REFERENCES green_beans(id),
    roast_date        TEXT NOT NULL,
    input_weight_g    REAL NOT NULL,
    output_weight_g   REAL,
    moisture_loss_pct REAL,
    roast_level       TEXT,
    notes             TEXT,
    coffee_id         INTEGER REFERENCES coffees(id),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_roasting_bean ON roasting_logs(green_bean_id);
CREATE INDEX IF NOT EXISTS idx_roasting_date ON roasting_logs(roast_date DESC);

CREATE TABLE IF NOT EXISTS pricing (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    green_bean_id   INTEGER NOT NULL REFERENCES green_beans(id),
    weight_g        INTEGER NOT NULL,
    retail_price    INTEGER NOT NULL,
    wholesale_price INTEGER,
    is_active       INTEGER DEFAULT 1,
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(green_bean_id, weight_g)
);

CREATE TABLE IF NOT EXISTS blends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS blend_components (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    blend_id        INTEGER NOT NULL REFERENCES blends(id) ON DELETE CASCADE,
    green_bean_id   INTEGER NOT NULL REFERENCES green_beans(id),
    ratio_pct       REAL NOT NULL,
    UNIQUE(blend_id, green_bean_id)
);
"""

_EXTRA_COLUMNS = (
    ("category", "TEXT"),
    ("brewed_at", "INTEGER"),
    ("roast_point", "INTEGER"),
    ("availability", "TEXT DEFAULT '운영'"),
    ("green_bean_id", "INTEGER REFERENCES green_beans(id)"),
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
        conn.executescript(GREEN_BEAN_SCHEMA)
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
        # feedback.coffee_name 컬럼 보장 + 기존 행 백필 + 인덱스
        fb_cols = {r["name"] for r in conn.execute("PRAGMA table_info(feedback)").fetchall()}
        if "coffee_name" not in fb_cols:
            conn.execute("ALTER TABLE feedback ADD COLUMN coffee_name TEXT")
        conn.execute(
            "UPDATE feedback "
            "SET coffee_name = (SELECT name FROM coffees WHERE coffees.id = feedback.coffee_id) "
            "WHERE coffee_name IS NULL OR coffee_name = ''"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_name "
            "ON feedback(coffee_name, created_at DESC)"
        )
        # 생두 관리 초기 데이터 시드 (스프레드시트 마이그레이션 — 1회만)
        if not conn.execute(
            "SELECT 1 FROM migrations WHERE name=?", ("seed_green_beans_v1",)
        ).fetchone():
            seed_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "scripts", "seed_green_beans.sql"
            )
            if os.path.isfile(seed_path):
                with open(seed_path, "r", encoding="utf-8") as f:
                    sql = f.read()
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO migrations (name) VALUES (?)", ("seed_green_beans_v1",)
                )


# ---------- PIN brute-force 카운터 (워커 공유 영속) ----------

def pin_check_lock(ip: str) -> int:
    """잠겨 있으면 남은 초, 아니면 0."""
    now = time.time()
    with connect() as conn:
        row = conn.execute(
            "SELECT locked_until FROM pin_attempts WHERE ip=?", (ip,)
        ).fetchone()
        if row and row["locked_until"] > now:
            return int(row["locked_until"] - now)
    return 0


def pin_record_failure(ip: str, max_attempts: int, window_sec: int, lock_sec: int):
    """실패 기록. 반환 (count, lock_remaining_sec).
    lock_remaining_sec > 0이면 이번 실패로 잠김.
    """
    now = time.time()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT count, window_start FROM pin_attempts WHERE ip=?", (ip,)
        ).fetchone()
        if row is None or now - row["window_start"] > window_sec:
            count = 1
            window_start = now
        else:
            count = row["count"] + 1
            window_start = row["window_start"]
        locked_until = now + lock_sec if count >= max_attempts else 0.0
        conn.execute(
            "INSERT INTO pin_attempts(ip, count, window_start, locked_until) "
            "VALUES(?,?,?,?) "
            "ON CONFLICT(ip) DO UPDATE SET "
            "count=excluded.count, window_start=excluded.window_start, "
            "locked_until=excluded.locked_until",
            (ip, count, window_start, locked_until),
        )
        conn.execute("COMMIT")
        return count, max(0, int(locked_until - now))


def pin_reset(ip: str):
    with connect() as conn:
        conn.execute("DELETE FROM pin_attempts WHERE ip=?", (ip,))


def _date_obj(s: Optional[str]):
    """Return Notion-compatible date object or None."""
    if not s:
        return None
    return {"start": s, "end": None}


_STATUS_ORDER = {"예정": 0, "진행 중": 1, "완료": 2}


def _compute_display_status(raw: Optional[str], serve_date: Optional[str]) -> Optional[str]:
    """제공일 기준으로 상태 자동 진행. 관리자 수동값(raw)이 더 진행돼 있으면 그쪽 보존.

    예) raw=예정 + serve=오늘 → '진행 중'
        raw=예정 + serve=어제 → '완료'
        raw=완료 + serve=내일 → '완료' (관리자가 일찍 마감한 경우 보존)
    """
    if not serve_date:
        return raw
    today = date.today().isoformat()
    if serve_date > today:
        natural = "예정"
    elif serve_date == today:
        natural = "진행 중"
    else:
        natural = "완료"
    raw_key = raw or "예정"
    raw_o = _STATUS_ORDER.get(raw_key, 0)
    nat_o = _STATUS_ORDER.get(natural, 0)
    return natural if nat_o > raw_o else raw_key


def _row_to_api(row: sqlite3.Row) -> dict:
    """Convert DB row to API response (Korean keys, Notion-compatible shape)."""
    return {
        "id": row["id"],
        "커피": row["name"],
        "로스터리": row["roastery"],
        "로스팅": _date_obj(row["roast_date"]),
        "프로세싱": row["process"],
        "상태": _compute_display_status(row["status"], row["serve_date"]),
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
    """현재 '진행 중' 항목과 히스토리를 한글 키로 반환.

    공개용: '완료' 항목은 최근 3개월 이내(제공일 우선, 없으면 로스팅일)만 노출.
    예정 항목은 향후 일정이므로 기간 필터 없이 모두 노출.
    진행 중 항목은 '지금 제공 중' 카드와 히스토리 리스트 양쪽에 노출되며,
    히스토리 리스트에서는 우선순위 1번이 된다.

    히스토리 정렬 우선순위:
      1) 진행 중 (제공중인 커피)
      2) 예정 + 미래 제공일 — 오늘과 가까운 제공일 순(오름차순)
      3) 그 외 — 로스팅 최신순(내림차순)
    동순위 내 동률은 이름 가나다순.
    """
    today = []
    history = []
    cutoff = _months_ago_iso(3)
    today_iso = date.today().isoformat()

    with connect() as conn:
        rows = conn.execute("SELECT * FROM coffees").fetchall()

    items = [_row_to_api(r) for r in rows]

    for item in items:
        if not item.get("커피"):
            continue
        status = item.get("상태")
        if status == "진행 중":
            today.append(item)
            history.append(item)
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
        serve = (item.get("제공일") or {}).get("start") or ""
        roast = (item.get("로스팅") or {}).get("start") or ""
        name = item.get("커피") or ""
        roast_ts = _date_to_ts(roast)
        serve_ts = _date_to_ts(serve)
        if status == "진행 중":
            return (0, -roast_ts, name)
        if status == "예정" and serve and serve >= today_iso:
            return (1, serve_ts, name)
        return (2, -roast_ts, name)

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


# ---------- 방문자 통계 ----------

def record_visit(visitor_id: str, path: str, device: str, is_new: int, ts_utc: str) -> None:
    """단일 페이지뷰 기록. date_kst, hour_kst 는 ts_utc 에서 +9h."""
    from datetime import datetime, timedelta
    dt_utc = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
    dt_kst = dt_utc + timedelta(hours=9)
    date_kst = dt_kst.strftime("%Y-%m-%d")
    hour_kst = dt_kst.hour
    with connect() as conn:
        conn.execute(
            "INSERT INTO visits (ts, date_kst, hour_kst, path, visitor_id, device, is_new) "
            "VALUES (?,?,?,?,?,?,?)",
            (ts_utc, date_kst, hour_kst, path, visitor_id, device, int(bool(is_new))),
        )


def stats_summary() -> dict:
    """오늘/전체 unique 방문자, 시간별 (오늘 KST), 디바이스 분포 (오늘 KST)."""
    from datetime import datetime, timedelta, timezone
    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    today_kst = now_kst.strftime("%Y-%m-%d")
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT visitor_id) AS c FROM visits WHERE date_kst=?",
            (today_kst,),
        ).fetchone()
        today_uniques = row["c"] if row else 0
        row = conn.execute(
            "SELECT COUNT(DISTINCT visitor_id) AS c FROM visits"
        ).fetchone()
        total_uniques = row["c"] if row else 0
        row = conn.execute("SELECT COUNT(*) AS c FROM visits").fetchone()
        total_pv = row["c"] if row else 0
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM visits WHERE date_kst=?", (today_kst,)
        ).fetchone()
        today_pv = row["c"] if row else 0
        # 시간별 (오늘 KST)
        rows = conn.execute(
            "SELECT hour_kst, COUNT(DISTINCT visitor_id) AS c FROM visits "
            "WHERE date_kst=? GROUP BY hour_kst",
            (today_kst,),
        ).fetchall()
        hourly_map = {r["hour_kst"]: r["c"] for r in rows}
        hourly = [{"hour": h, "count": hourly_map.get(h, 0)} for h in range(24)]
        # 디바이스 분포 (오늘 KST)
        rows = conn.execute(
            "SELECT device, COUNT(DISTINCT visitor_id) AS c FROM visits "
            "WHERE date_kst=? GROUP BY device",
            (today_kst,),
        ).fetchall()
        devices = {r["device"]: r["c"] for r in rows}
    return {
        "today_kst": today_kst,
        "today_uniques": today_uniques,
        "today_pv": today_pv,
        "total_uniques": total_uniques,
        "total_pv": total_pv,
        "hourly_kst": hourly,
        "devices": devices,
    }


# ---------- 피드백 ----------

def feedback_recent_count_by_ip(ip_hash: str, window_sec: int) -> int:
    """현재 시각으로부터 window_sec 초 이내 동일 IP의 제출 건수.

    created_at 는 'YYYY-MM-DDTHH:MM:SSZ' ISO 문자열이라 사전식 비교로 충분.
    """
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(seconds=window_sec)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM feedback WHERE ip_hash=? AND created_at > ?",
            (ip_hash, cutoff),
        ).fetchone()
    return row["c"] if row else 0


def create_feedback(coffee_id: int, nickname: str, rating: int,
                    cup_notes_json: str, comment: str, ip_hash: str,
                    coffee_name: Optional[str] = None) -> int:
    """피드백 1건 저장.

    coffee_name 은 제출 시점의 원두 이름 스냅샷. 재입고/복제 등으로 새 row 가
    생겨도 같은 이름의 모든 row 에서 피드백을 함께 조회/참조 가능.
    호출자가 명시하지 않으면 coffee_id 로 찾아서 채운다.
    """
    with connect() as conn:
        if not coffee_name:
            row = conn.execute(
                "SELECT name FROM coffees WHERE id=?", (coffee_id,)
            ).fetchone()
            coffee_name = row["name"] if row else None
        cur = conn.execute(
            "INSERT INTO feedback "
            "(coffee_id, coffee_name, nickname, rating, cup_notes_json, comment, ip_hash) "
            "VALUES (?,?,?,?,?,?,?)",
            (coffee_id, coffee_name or None, nickname or None, rating,
             cup_notes_json or None, comment or None, ip_hash or None),
        )
        return cur.lastrowid


def _feedback_row_to_dict(row: sqlite3.Row) -> dict:
    import json as _json
    notes = []
    if row["cup_notes_json"]:
        try:
            notes = _json.loads(row["cup_notes_json"])
            if not isinstance(notes, list):
                notes = []
        except (ValueError, TypeError):
            notes = []
    return {
        "id": row["id"],
        "coffee_id": row["coffee_id"],
        "coffee_name": row["coffee_name"] if "coffee_name" in row.keys() else None,
        "nickname": row["nickname"] or "",
        "rating": row["rating"],
        "cup_notes": notes,
        "comment": row["comment"] or "",
        "created_at": row["created_at"],
    }


def _resolve_coffee_name(conn, coffee_id: int) -> Optional[str]:
    row = conn.execute("SELECT name FROM coffees WHERE id=?", (coffee_id,)).fetchone()
    return row["name"] if row else None


def list_feedback_for_coffee(coffee_id: int, limit: int = 100) -> list:
    """공개 노출용. ip_hash 는 응답에 포함하지 않음.

    피드백은 원두 이름 기준으로 묶인다 — 같은 이름의 다른 row 에 달린 피드백도
    함께 반환. (재입고/복제로 새 row 가 만들어져도 과거 피드백을 계속 보여주기 위함)
    """
    with connect() as conn:
        name = _resolve_coffee_name(conn, coffee_id)
        if name:
            rows = conn.execute(
                "SELECT id, coffee_id, coffee_name, nickname, rating, cup_notes_json, "
                "       comment, created_at FROM feedback "
                "WHERE coffee_name = ? OR coffee_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (name, coffee_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, coffee_id, coffee_name, nickname, rating, cup_notes_json, "
                "       comment, created_at FROM feedback "
                "WHERE coffee_id=? ORDER BY created_at DESC LIMIT ?",
                (coffee_id, limit),
            ).fetchall()
    return [_feedback_row_to_dict(r) for r in rows]


def list_feedback_all(limit: int = 500) -> list:
    """관리자용. coffee_name 은 스냅샷 우선, 없으면 현재 커피 이름으로 채움."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT f.id, f.coffee_id, f.nickname, f.rating, f.cup_notes_json, "
            "       f.comment, f.created_at, "
            "       COALESCE(f.coffee_name, c.name) AS coffee_name "
            "FROM feedback f "
            "LEFT JOIN coffees c ON c.id = f.coffee_id "
            "ORDER BY f.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_feedback_row_to_dict(r) for r in rows]


def delete_feedback(feedback_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM feedback WHERE id=?", (feedback_id,))
        return cur.rowcount > 0


def update_feedback(feedback_id: int, rating: Optional[int] = None,
                    comment: Optional[str] = None,
                    nickname: Optional[str] = None) -> bool:
    """관리자용 — rating/comment/nickname 수정. None 은 변경 안 함."""
    sets = []
    values: list = []
    if rating is not None:
        sets.append("rating=?")
        values.append(int(rating))
    if comment is not None:
        sets.append("comment=?")
        values.append(comment or None)
    if nickname is not None:
        sets.append("nickname=?")
        values.append(nickname or None)
    if not sets:
        return False
    values.append(feedback_id)
    with connect() as conn:
        cur = conn.execute(
            f"UPDATE feedback SET {','.join(sets)} WHERE id=?", values
        )
        return cur.rowcount > 0


def popular_cup_notes(limit: int = 20) -> list:
    """coffees.cup_notes 전체에서 개별 향미를 빈도 내림차순으로 반환.

    동일 빈도는 가나다순(안정 정렬). 피드백 모달의 토큰 후보로 사용.
    """
    import re as _re
    from collections import Counter
    with connect() as conn:
        rows = conn.execute(
            "SELECT cup_notes FROM coffees "
            "WHERE cup_notes IS NOT NULL AND cup_notes != ''"
        ).fetchall()
    counter: Counter = Counter()
    for r in rows:
        for note in _re.split(r"[,/\n;|]", r["cup_notes"] or ""):
            note = note.strip()
            if note:
                counter[note] += 1
    return [n for n, _ in sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:limit]]


def feedback_summary_for_coffee(coffee_id: int) -> dict:
    """공개 노출용 요약 — 평균 별점, 건수, 가장 많이 선택된 컵노트 top 5.

    동일 원두 이름의 모든 row 에 달린 피드백을 합산.
    """
    import json as _json
    with connect() as conn:
        name = _resolve_coffee_name(conn, coffee_id)
        if name:
            where_sql = "WHERE (coffee_name = ? OR coffee_id = ?)"
            where_args: tuple = (name, coffee_id)
        else:
            where_sql = "WHERE coffee_id = ?"
            where_args = (coffee_id,)
        row = conn.execute(
            f"SELECT COUNT(*) AS c, AVG(rating) AS avg_rating FROM feedback {where_sql}",
            where_args,
        ).fetchone()
        count = row["c"] if row else 0
        avg = float(row["avg_rating"]) if row and row["avg_rating"] is not None else 0.0
        rows = conn.execute(
            f"SELECT cup_notes_json FROM feedback {where_sql} "
            "AND cup_notes_json IS NOT NULL",
            where_args,
        ).fetchall()
    tallies: dict[str, int] = {}
    for r in rows:
        try:
            arr = _json.loads(r["cup_notes_json"])
            if isinstance(arr, list):
                for note in arr:
                    if isinstance(note, str) and note.strip():
                        k = note.strip()
                        tallies[k] = tallies.get(k, 0) + 1
        except (ValueError, TypeError):
            continue
    top_notes = sorted(tallies.items(), key=lambda x: (-x[1], x[0]))[:5]
    return {
        "count": count,
        "avg_rating": round(avg, 2),
        "top_notes": [{"note": k, "count": v} for k, v in top_notes],
    }


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


# ---------- 공급업체 ----------

def list_suppliers() -> list:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_supplier(sid: int) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM suppliers WHERE id=?", (sid,)).fetchone()
    return dict(row) if row else None


def create_supplier(data: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO suppliers (name, short_name, contact, notes) VALUES (?,?,?,?)",
            (data["name"], data.get("short_name"), data.get("contact"), data.get("notes")),
        )
        return cur.lastrowid


def update_supplier(sid: int, data: dict) -> bool:
    sets, vals = [], []
    for k in ("name", "short_name", "contact", "notes"):
        if k in data:
            sets.append(f"{k}=?")
            vals.append(data[k])
    if not sets:
        return False
    sets.append("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
    vals.append(sid)
    with connect() as conn:
        cur = conn.execute(f"UPDATE suppliers SET {','.join(sets)} WHERE id=?", vals)
        return cur.rowcount > 0


def delete_supplier(sid: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM suppliers WHERE id=?", (sid,))
        return cur.rowcount > 0


# ---------- 생두 마스터 ----------

def _gb_row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["display_name"] = d["name"]
    return d


def list_green_beans(include_inactive: bool = False) -> list:
    where = "" if include_inactive else "WHERE gb.status='활성'"
    sql = f"""
        SELECT gb.*, s.name AS supplier_name, s.short_name AS supplier_short,
            COALESCE(p_sum.purchased_kg, 0) AS purchased_kg,
            COALESCE(r_sum.used_kg, 0) AS used_kg,
            COALESCE(p_sum.purchased_kg, 0) - COALESCE(r_sum.used_kg, 0) AS remaining_kg,
            COALESCE(p_sum.avg_unit_price, 0) AS avg_unit_price
        FROM green_beans gb
        LEFT JOIN suppliers s ON s.id = gb.supplier_id
        LEFT JOIN (
            SELECT green_bean_id,
                   SUM(quantity_kg) AS purchased_kg,
                   ROUND(CAST(SUM(total_price) AS REAL) / NULLIF(SUM(quantity_kg), 0)) AS avg_unit_price
            FROM purchases GROUP BY green_bean_id
        ) p_sum ON p_sum.green_bean_id = gb.id
        LEFT JOIN (
            SELECT green_bean_id, SUM(input_weight_g) / 1000.0 AS used_kg
            FROM roasting_logs GROUP BY green_bean_id
        ) r_sum ON r_sum.green_bean_id = gb.id
        {where}
        ORDER BY remaining_kg DESC, gb.name
    """
    with connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def get_green_bean(gb_id: int) -> Optional[dict]:
    sql = """
        SELECT gb.*, s.name AS supplier_name, s.short_name AS supplier_short,
            COALESCE(p_sum.purchased_kg, 0) AS purchased_kg,
            COALESCE(r_sum.used_kg, 0) AS used_kg,
            COALESCE(p_sum.purchased_kg, 0) - COALESCE(r_sum.used_kg, 0) AS remaining_kg,
            COALESCE(p_sum.avg_unit_price, 0) AS avg_unit_price,
            COALESCE(r_sum.avg_loss_pct, 0) AS avg_loss_pct
        FROM green_beans gb
        LEFT JOIN suppliers s ON s.id = gb.supplier_id
        LEFT JOIN (
            SELECT green_bean_id,
                   SUM(quantity_kg) AS purchased_kg,
                   ROUND(CAST(SUM(total_price) AS REAL) / NULLIF(SUM(quantity_kg), 0)) AS avg_unit_price
            FROM purchases GROUP BY green_bean_id
        ) p_sum ON p_sum.green_bean_id = gb.id
        LEFT JOIN (
            SELECT green_bean_id,
                   SUM(input_weight_g) / 1000.0 AS used_kg,
                   AVG(moisture_loss_pct) AS avg_loss_pct
            FROM roasting_logs GROUP BY green_bean_id
        ) r_sum ON r_sum.green_bean_id = gb.id
        WHERE gb.id = ?
    """
    with connect() as conn:
        row = conn.execute(sql, (gb_id,)).fetchone()
    return dict(row) if row else None


def create_green_bean(data: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO green_beans "
            "(name, supplier_id, origin_country, origin_region, process, grade, "
            " cup_notes, description, is_decaf, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                data["name"], data.get("supplier_id"), data.get("origin_country"),
                data.get("origin_region"), data["process"], data.get("grade"),
                data.get("cup_notes"), data.get("description"),
                data.get("is_decaf", 0), data.get("status", "활성"),
            ),
        )
        return cur.lastrowid


def update_green_bean(gb_id: int, data: dict) -> bool:
    allowed = ("name", "supplier_id", "origin_country", "origin_region",
               "process", "grade", "cup_notes", "description", "is_decaf", "status")
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f"{k}=?")
            vals.append(data[k])
    if not sets:
        return False
    sets.append("updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')")
    vals.append(gb_id)
    with connect() as conn:
        cur = conn.execute(f"UPDATE green_beans SET {','.join(sets)} WHERE id=?", vals)
        return cur.rowcount > 0


def delete_green_bean(gb_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("UPDATE green_beans SET status='단종' WHERE id=?", (gb_id,))
        return cur.rowcount > 0


def green_bean_suggestions() -> dict:
    with connect() as conn:
        suppliers = conn.execute(
            "SELECT id, name, short_name FROM suppliers ORDER BY name"
        ).fetchall()
        processes = conn.execute(
            "SELECT DISTINCT process FROM green_beans WHERE process IS NOT NULL AND process != '' ORDER BY process"
        ).fetchall()
        grades = conn.execute(
            "SELECT DISTINCT grade FROM green_beans WHERE grade IS NOT NULL AND grade != '' ORDER BY grade"
        ).fetchall()
        origins = conn.execute(
            "SELECT DISTINCT origin_country FROM green_beans WHERE origin_country IS NOT NULL AND origin_country != '' ORDER BY origin_country"
        ).fetchall()
    return {
        "suppliers": [dict(r) for r in suppliers],
        "processes": [r["process"] for r in processes],
        "grades": [r["grade"] for r in grades],
        "origins": [r["origin_country"] for r in origins],
    }


# ---------- 구매 ----------

def list_purchases(green_bean_id: Optional[int] = None, limit: int = 200) -> list:
    sql = """
        SELECT p.*, gb.name AS bean_name, s.short_name AS supplier_short
        FROM purchases p
        JOIN green_beans gb ON gb.id = p.green_bean_id
        LEFT JOIN suppliers s ON s.id = gb.supplier_id
    """
    args: list = []
    if green_bean_id:
        sql += " WHERE p.green_bean_id = ?"
        args.append(green_bean_id)
    sql += " ORDER BY p.purchase_date DESC, p.id DESC LIMIT ?"
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def create_purchase(data: dict) -> int:
    qty = float(data["quantity_kg"])
    price = int(data["unit_price"])
    discount = int(data.get("discount") or 0)
    total = int(qty * price) - discount
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO purchases "
            "(green_bean_id, purchase_date, quantity_kg, unit_price, discount, total_price, lot_number, notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                int(data["green_bean_id"]), data["purchase_date"],
                qty, price, discount, total,
                data.get("lot_number"), data.get("notes"),
            ),
        )
        return cur.lastrowid


def update_purchase(pid: int, data: dict) -> bool:
    allowed = ("green_bean_id", "purchase_date", "quantity_kg", "unit_price",
               "discount", "lot_number", "notes")
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f"{k}=?")
            vals.append(data[k])
    if "quantity_kg" in data or "unit_price" in data or "discount" in data:
        with connect() as conn:
            row = conn.execute("SELECT * FROM purchases WHERE id=?", (pid,)).fetchone()
        if not row:
            return False
        qty = float(data.get("quantity_kg", row["quantity_kg"]))
        price = int(data.get("unit_price", row["unit_price"]))
        disc = int(data.get("discount", row["discount"] or 0))
        sets.append("total_price=?")
        vals.append(int(qty * price) - disc)
    if not sets:
        return False
    vals.append(pid)
    with connect() as conn:
        cur = conn.execute(f"UPDATE purchases SET {','.join(sets)} WHERE id=?", vals)
        return cur.rowcount > 0


def delete_purchase(pid: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM purchases WHERE id=?", (pid,))
        return cur.rowcount > 0


# ---------- 로스팅 로그 ----------

def list_roasting_logs(green_bean_id: Optional[int] = None, limit: int = 200) -> list:
    sql = """
        SELECT r.*, gb.name AS bean_name, s.short_name AS supplier_short
        FROM roasting_logs r
        JOIN green_beans gb ON gb.id = r.green_bean_id
        LEFT JOIN suppliers s ON s.id = gb.supplier_id
    """
    args: list = []
    if green_bean_id:
        sql += " WHERE r.green_bean_id = ?"
        args.append(green_bean_id)
    sql += " ORDER BY r.roast_date DESC, r.id DESC LIMIT ?"
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def create_roasting_log(data: dict) -> int:
    input_g = float(data["input_weight_g"])
    output_g = float(data["output_weight_g"]) if data.get("output_weight_g") else None
    loss = None
    if output_g is not None and input_g > 0:
        loss = round((1 - output_g / input_g) * 100, 2)
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO roasting_logs "
            "(green_bean_id, roast_date, input_weight_g, output_weight_g, "
            " moisture_loss_pct, roast_level, notes, coffee_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                int(data["green_bean_id"]), data["roast_date"],
                input_g, output_g, loss,
                data.get("roast_level"), data.get("notes"),
                data.get("coffee_id"),
            ),
        )
        return cur.lastrowid


def update_roasting_log(rid: int, data: dict) -> bool:
    allowed = ("green_bean_id", "roast_date", "input_weight_g", "output_weight_g",
               "roast_level", "notes", "coffee_id")
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f"{k}=?")
            vals.append(data[k])
    if "input_weight_g" in data or "output_weight_g" in data:
        with connect() as conn:
            row = conn.execute("SELECT * FROM roasting_logs WHERE id=?", (rid,)).fetchone()
        if not row:
            return False
        inp = float(data.get("input_weight_g", row["input_weight_g"]))
        out = data.get("output_weight_g", row["output_weight_g"])
        out = float(out) if out is not None else None
        loss = round((1 - out / inp) * 100, 2) if out is not None and inp > 0 else None
        sets.append("moisture_loss_pct=?")
        vals.append(loss)
    if not sets:
        return False
    vals.append(rid)
    with connect() as conn:
        cur = conn.execute(f"UPDATE roasting_logs SET {','.join(sets)} WHERE id=?", vals)
        return cur.rowcount > 0


def delete_roasting_log(rid: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM roasting_logs WHERE id=?", (rid,))
        return cur.rowcount > 0


# ---------- 재고 (computed) ----------

def inventory_list() -> list:
    """재고 목록. 정렬: 재고>0인 것 먼저 (최근 구매일→재고 많은 순), 재고≤0은 아래로.
    각 항목에 last_purchase_date, is_stale(재고0+구매1년이상) 포함."""
    sql = """
        SELECT gb.id, gb.name, gb.process, gb.grade, gb.is_decaf, gb.status,
            s.name AS supplier_name, s.short_name AS supplier_short,
            COALESCE(p_sum.purchased_kg, 0) AS purchased_kg,
            COALESCE(r_sum.used_kg, 0) AS used_kg,
            COALESCE(p_sum.purchased_kg, 0) - COALESCE(r_sum.used_kg, 0) AS remaining_kg,
            COALESCE(p_sum.avg_unit_price, 0) AS avg_unit_price,
            p_sum.last_purchase_date
        FROM green_beans gb
        LEFT JOIN suppliers s ON s.id = gb.supplier_id
        LEFT JOIN (
            SELECT green_bean_id,
                   SUM(quantity_kg) AS purchased_kg,
                   ROUND(CAST(SUM(total_price) AS REAL) / NULLIF(SUM(quantity_kg), 0)) AS avg_unit_price,
                   MAX(purchase_date) AS last_purchase_date
            FROM purchases GROUP BY green_bean_id
        ) p_sum ON p_sum.green_bean_id = gb.id
        LEFT JOIN (
            SELECT green_bean_id, SUM(input_weight_g) / 1000.0 AS used_kg
            FROM roasting_logs GROUP BY green_bean_id
        ) r_sum ON r_sum.green_bean_id = gb.id
        WHERE gb.status = '활성'
        ORDER BY
            CASE WHEN (COALESCE(p_sum.purchased_kg,0) - COALESCE(r_sum.used_kg,0)) > 0 THEN 0 ELSE 1 END,
            p_sum.last_purchase_date DESC,
            (COALESCE(p_sum.purchased_kg,0) - COALESCE(r_sum.used_kg,0)) DESC
    """
    cutoff = _months_ago_iso(12)
    with connect() as conn:
        rows = conn.execute(sql).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        lpd = d.get("last_purchase_date") or ""
        d["is_stale"] = 1 if (d["remaining_kg"] <= 0 and lpd < cutoff) else 0
        result.append(d)
    return result


# ---------- 가격 ----------

def list_pricing(green_bean_id: Optional[int] = None) -> list:
    sql = """
        SELECT pr.*, gb.name AS bean_name, s.short_name AS supplier_short
        FROM pricing pr
        JOIN green_beans gb ON gb.id = pr.green_bean_id
        LEFT JOIN suppliers s ON s.id = gb.supplier_id
    """
    args: list = []
    if green_bean_id:
        sql += " WHERE pr.green_bean_id = ?"
        args.append(green_bean_id)
    sql += " ORDER BY gb.name, pr.weight_g"
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def upsert_pricing(data: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO pricing (green_bean_id, weight_g, retail_price, wholesale_price) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(green_bean_id, weight_g) DO UPDATE SET "
            "retail_price=excluded.retail_price, wholesale_price=excluded.wholesale_price, "
            "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
            (
                int(data["green_bean_id"]), int(data["weight_g"]),
                int(data["retail_price"]), data.get("wholesale_price"),
            ),
        )
        return cur.lastrowid


def delete_pricing(pid: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM pricing WHERE id=?", (pid,))
        return cur.rowcount > 0


def cost_analysis(gb_id: int) -> dict:
    gb = get_green_bean(gb_id)
    if not gb:
        return {}
    avg_price = gb.get("avg_unit_price") or 0
    avg_loss = gb.get("avg_loss_pct") or 0
    yield_ratio = (100 - avg_loss) / 100 if avg_loss < 100 else 0
    roasted_cost_per_kg = int(avg_price / yield_ratio) if yield_ratio > 0 else 0
    roasted_cost_per_g = round(roasted_cost_per_kg / 1000, 2) if roasted_cost_per_kg else 0
    espresso_20g = round(roasted_cost_per_g * 20, 0)
    return {
        "green_bean": gb,
        "avg_green_cost_per_kg": avg_price,
        "avg_loss_pct": round(avg_loss, 2),
        "yield_ratio": round(yield_ratio, 4),
        "roasted_cost_per_kg": roasted_cost_per_kg,
        "roasted_cost_per_g": roasted_cost_per_g,
        "espresso_20g_cost": espresso_20g,
        "pricing": list_pricing(gb_id),
    }
