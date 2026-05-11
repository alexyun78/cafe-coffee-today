"""오늘의 커피 — Flask 백엔드 (SQLite + PIN 관리자).

공개 엔드포인트는 GET /, GET /api/coffee, GET /apk.
관리 엔드포인트는 세션 기반 PIN 인증 필요.
"""
import io
import json
import os
import re
import secrets
import time
from datetime import date, datetime, timezone
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    request,
    send_file,
    send_from_directory,
    session,
)
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db

ADMIN_PIN = os.environ.get("ADMIN_PIN", "")
FLASK_SECRET = os.environ.get("FLASK_SECRET", "dev-secret-change-me")
ADMIN_ALIAS_PATH = os.environ.get("ADMIN_ALIAS_PATH", "").strip()
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]

if not ADMIN_PIN:
    raise ValueError(
        "❌ ADMIN_PIN 환경 변수가 설정되지 않았습니다. .env에 ADMIN_PIN을 추가하세요."
    )

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = FLASK_SECRET
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
)
if ALLOWED_ORIGINS:
    CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)
else:
    CORS(app, supports_credentials=True)

db.init_schema()


# ---------- 방문자 추적 ----------
# 쿠키 기반 (IP 저장 X). 공개 페이지만 카운트. 봇 UA 제외.

VISIT_COOKIE = "vid"
VISIT_COOKIE_TTL = 86400  # 1일 — 자정 KST 가 아니라 첫 방문 후 24h. 단순함을 위해.

_BOT_RE = re.compile(
    r"bot|crawler|spider|crawl|http://|googlebot|bingbot|yandex|duckduck|"
    r"baiduspider|slurp|facebookexternalhit|whatsapp|telegrambot|"
    r"applebot|amazonbot|petalbot|semrushbot|ahrefsbot|mj12bot|"
    r"headlesschrome|phantomjs|puppeteer|playwright|selenium",
    re.I,
)

# 공개 페이지 화이트리스트. /admin, /api, /static, /downloads 는 카운트 X.
_TRACK_PATH_RE = re.compile(
    r"^/(?:$|insight(?:/|$)|apk(?:/|$)|game(?:-apk)?(?:/|$)|today(?:/|$)|roastery(?:/|$))"
)

_VID_RE = re.compile(r"^[A-Za-z0-9_-]{8,40}$")


def _classify_device(ua: str) -> str:
    ua_l = (ua or "").lower()
    if not ua_l:
        return "desktop"
    if _BOT_RE.search(ua_l):
        return "bot"
    if "ipad" in ua_l or ("android" in ua_l and "mobile" not in ua_l):
        return "tablet"
    if any(s in ua_l for s in ("mobile", "iphone", "ipod", "android")):
        return "mobile"
    return "desktop"


@app.before_request
def _track_visit():
    if request.method != "GET":
        return
    path = request.path
    if not _TRACK_PATH_RE.match(path):
        return
    ua = request.headers.get("User-Agent", "")
    device = _classify_device(ua)
    if device == "bot":
        return
    vid = request.cookies.get(VISIT_COOKIE) or ""
    is_new = 0
    if not _VID_RE.match(vid):
        vid = secrets.token_urlsafe(12)
        is_new = 1
        g.set_vid = vid
    try:
        ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.record_visit(vid, path, device, is_new, ts_utc)
    except Exception:
        # 통계는 보조 기능 — 실패해도 요청 본 흐름은 절대 막지 않음
        pass


# ---------- 보안 헤더 ----------

@app.after_request
def add_security_headers(resp):
    vid = getattr(g, "set_vid", None)
    if vid:
        resp.set_cookie(
            VISIT_COOKIE,
            vid,
            max_age=VISIT_COOKIE_TTL,
            httponly=True,
            samesite="Lax",
            secure=SESSION_COOKIE_SECURE,
            path="/",
        )
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    return resp


# ---------- PIN brute-force 방지 (sqlite, 워커 공유) ----------

PIN_MAX_ATTEMPTS = 5
PIN_WINDOW_SEC = 300      # 5분 동안 누적
PIN_LOCK_SEC = 900        # 임계 도달 시 15분 잠금


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


# ---------- 인증 ----------
# 두 가지 인증 경로 병행:
#   (1) 세션 쿠키 (브라우저용 — Flask 기본)
#   (2) Authorization: Bearer <token> 헤더 (APK용 — WebView 쿠키 불안정 대응)
# 토큰은 itsdangerous로 FLASK_SECRET 서명 + TTL 보장. 서버 측 상태 없음.

ADMIN_TOKEN_TTL_SEC = 60 * 60 * 24 * 7  # 7일
ADMIN_TOKEN_SALT = "admin-token-v1"
_token_serializer = URLSafeTimedSerializer(FLASK_SECRET, salt=ADMIN_TOKEN_SALT)


def _issue_admin_token() -> str:
    return _token_serializer.dumps({"admin": True})


def _bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return None


def _is_admin_authed() -> bool:
    if session.get("admin"):
        return True
    tok = _bearer_token()
    if not tok:
        return False
    try:
        data = _token_serializer.loads(tok, max_age=ADMIN_TOKEN_TTL_SEC)
        return bool(isinstance(data, dict) and data.get("admin"))
    except (BadSignature, SignatureExpired):
        return False


def require_pin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _is_admin_authed():
            return jsonify({"success": False, "error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


@app.post("/api/admin/verify")
def admin_verify():
    ip = _client_ip()
    locked = db.pin_check_lock(ip)
    if locked:
        return jsonify({
            "success": False, "error": "locked",
            "retry_after": locked, "max_attempts": PIN_MAX_ATTEMPTS,
        }), 429

    data = request.get_json(silent=True) or {}
    pin = (data.get("pin") or "").strip()
    if pin and pin == ADMIN_PIN:
        session["admin"] = True
        db.pin_reset(ip)
        return jsonify({"success": True, "token": _issue_admin_token()})

    count, lock_remaining = db.pin_record_failure(
        ip, PIN_MAX_ATTEMPTS, PIN_WINDOW_SEC, PIN_LOCK_SEC
    )
    # 응답 시간 살짝 지연 — 타이밍 공격/스크립트 속도 저하
    time.sleep(0.4)

    if lock_remaining:
        return jsonify({
            "success": False, "error": "locked",
            "retry_after": lock_remaining, "max_attempts": PIN_MAX_ATTEMPTS,
        }), 429

    attempts_left = max(0, PIN_MAX_ATTEMPTS - count)
    return jsonify({
        "success": False, "error": "invalid pin",
        "attempts_left": attempts_left,
        "max_attempts": PIN_MAX_ATTEMPTS,
    }), 401


@app.post("/api/admin/logout")
def admin_logout():
    session.pop("admin", None)
    # 토큰은 stateless라 서버에서 무효화할 수 없음. 클라이언트가 localStorage에서 제거.
    return jsonify({"success": True})


@app.get("/api/admin/status")
def admin_status():
    return jsonify({"success": True, "authenticated": _is_admin_authed()})


@app.get("/api/admin/stats")
@require_pin
def admin_stats():
    return jsonify({"success": True, **db.stats_summary()})


# ---------- 공개 조회 ----------

@app.get("/api/coffee")
def get_coffee():
    try:
        today, history = db.list_today_and_history()
        return jsonify({"success": True, "today": today, "history": history})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- 관리자 CRUD ----------

@app.get("/api/coffee/all")
@require_pin
def api_list_all():
    return jsonify({"success": True, "items": db.list_all()})


@app.get("/api/coffee/<int:coffee_id>")
@require_pin
def api_get_one(coffee_id):
    item = db.get_by_id(coffee_id)
    if not item:
        return jsonify({"success": False, "error": "not found"}), 404
    return jsonify({"success": True, "item": item})


def _parse_payload(data: dict) -> dict:
    """API payload (한글 키 허용) → DB 컬럼."""
    def pick(*keys):
        for k in keys:
            if k in data and data[k] not in (None, ""):
                v = data[k]
                if isinstance(v, dict):
                    v = v.get("start")
                return v
        return None

    def pick_int(*keys):
        v = pick(*keys)
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return {
        "name": pick("name", "커피"),
        "roastery": pick("roastery", "로스터리"),
        "roast_date": pick("roast_date", "로스팅"),
        "process": pick("process", "프로세싱"),
        "status": pick("status", "상태"),
        "cup_notes": pick("cup_notes", "컵노트"),
        "comment": pick("comment", "감상"),
        "serve_date": pick("serve_date", "제공일"),
        "category": pick("category", "구분"),
        "brewed_at": pick_int("brewed_at", "BREWED AT"),
        "roast_point": pick_int("roast_point", "로스팅 포인트"),
        "availability": pick("availability", "운영상태"),
    }


@app.post("/api/coffee")
@require_pin
def api_create():
    data = request.get_json(silent=True) or {}
    parsed = _parse_payload(data)
    if not parsed.get("name"):
        return jsonify({"success": False, "error": "원두 이름(name)은 필수"}), 400
    if parsed.get("status") == "진행 중" and not parsed.get("serve_date"):
        parsed["serve_date"] = date.today().isoformat()
    new_id = db.create(parsed)
    if parsed.get("status") == "진행 중":
        db.complete_other_in_progress(new_id)
    return jsonify({"success": True, "id": new_id, "item": db.get_by_id(new_id)})


@app.put("/api/coffee/<int:coffee_id>")
@require_pin
def api_update(coffee_id):
    data = request.get_json(silent=True) or {}
    parsed = {k: v for k, v in _parse_payload(data).items() if v is not None or k in data}
    if parsed.get("status") == "진행 중" and not parsed.get("serve_date"):
        parsed["serve_date"] = date.today().isoformat()
    if not db.update(coffee_id, parsed):
        return jsonify({"success": False, "error": "not found or no changes"}), 404
    if parsed.get("status") == "진행 중":
        db.complete_other_in_progress(coffee_id)
    cascaded = 0
    if parsed.get("availability"):
        item = db.get_by_id(coffee_id)
        if item and item.get("커피"):
            cascaded = db.set_availability_by_name(item["커피"], parsed["availability"])
    return jsonify({"success": True, "item": db.get_by_id(coffee_id), "cascaded": cascaded})


@app.delete("/api/coffee/<int:coffee_id>")
@require_pin
def api_delete(coffee_id):
    if not db.delete(coffee_id):
        return jsonify({"success": False, "error": "not found"}), 404
    return jsonify({"success": True})


@app.get("/api/suggestions")
@require_pin
def api_suggestions():
    return jsonify({"success": True, **db.suggestions()})


@app.get("/api/coffee/<int:coffee_id>/card.png")
@require_pin
def api_card_png(coffee_id):
    item = db.get_by_id(coffee_id)
    if not item:
        return jsonify({"success": False, "error": "not found"}), 404
    try:
        from generate_bean_images import render_card_for_coffee
        img = render_card_for_coffee(item)
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    raw_name = item.get("커피") or "card"
    safe = re.sub(r'[\\/:*?"<>|]', "", raw_name).replace(" ", "_") or "card"
    return send_file(
        buf, mimetype="image/png", as_attachment=True,
        download_name=f"{safe}.png",
    )


# ---------- 정적 페이지 ----------

@app.get("/")
def index():
    return send_from_directory("static", "roastery.html")


@app.get("/today")
def today_page():
    return send_file("index.html")


def _serve_admin_form():
    """admin.html 응답. 인증 게이트는 admin.html init()이 /api/admin/status로 처리하고,
    실제 데이터/CRUD는 모두 @require_pin이 막는다. 따라서 HTML 자체는 무조건 응답해도 안전.
    """
    return send_from_directory("static", "admin.html")


@app.get("/admin")
def admin_page():
    return _serve_admin_form()


# 환경변수로 비공개 별칭 경로 추가 (.env: ADMIN_ALIAS_PATH=/a-7f2e91b3)
# 이 경로는 PIN 입력 진입점 — 인증되지 않아도 admin.html을 응답해 PIN 모달을 띄움.
if ADMIN_ALIAS_PATH and ADMIN_ALIAS_PATH.startswith("/") and ADMIN_ALIAS_PATH != "/admin":
    app.add_url_rule(ADMIN_ALIAS_PATH, "admin_alias", _serve_admin_form, methods=["GET"])


@app.get("/roastery")
def roastery_page():
    return send_from_directory("static", "roastery.html")


@app.get("/apk")
def apk_page():
    return send_from_directory("static", "apk.html")


# ---------- Coffee Insight ----------
# 컨텐츠는 static/insights/ 에 JSON + standalone HTML 형태로 살아 있고,
# GitHub Actions 워커가 매일 새 파일을 add/commit/push 한다.
# 여기서는 단순히 파일을 서빙하고 /api/insights 로 인덱스를 노출한다.

INSIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "insights")
INSIGHT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{0,127}$")


def _read_insight_index() -> dict:
    path = os.path.join(INSIGHTS_DIR, "index.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"version": 1, "items": []}


@app.get("/insight")
def insight_list_page():
    return send_from_directory("static", "insight-list.html")


@app.get("/insight/<insight_id>")
def insight_article_page(insight_id: str):
    if not INSIGHT_ID_RE.match(insight_id):
        return jsonify({"success": False, "error": "invalid id"}), 404
    filename = f"{insight_id}.html"
    full_path = os.path.join(INSIGHTS_DIR, filename)
    if not os.path.isfile(full_path):
        return jsonify({"success": False, "error": "not found"}), 404
    return send_from_directory(INSIGHTS_DIR, filename)


@app.get("/api/insights")
def api_insights_list():
    index = _read_insight_index()
    items = index.get("items") or []
    # 최신순 정렬 (date desc, then id desc)
    items = sorted(
        items,
        key=lambda x: (x.get("date") or "", x.get("id") or ""),
        reverse=True,
    )
    try:
        limit = int(request.args.get("limit", "") or 0)
    except ValueError:
        limit = 0
    if limit > 0:
        items = items[:limit]
    return jsonify({
        "success": True,
        "items": items,
        "updated_at": index.get("updated_at"),
    })


@app.get("/api/insights/<insight_id>")
def api_insights_get(insight_id: str):
    if not INSIGHT_ID_RE.match(insight_id):
        return jsonify({"success": False, "error": "invalid id"}), 404
    path = os.path.join(INSIGHTS_DIR, f"{insight_id}.json")
    if not os.path.isfile(path):
        return jsonify({"success": False, "error": "not found"}), 404
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": True, "item": data})


@app.get("/game")
def game_page():
    return send_from_directory("static", "game.html")


@app.get("/game-apk")
def game_apk_page():
    return send_from_directory("static", "game-apk.html")


@app.get("/api/app-version")
def api_app_version():
    try:
        return send_file("cafe-coffee-apk/www/version.json")
    except Exception:
        return jsonify({"version": None}), 404


@app.get("/downloads/<path:name>")
def downloads(name):
    return send_from_directory("static/downloads", name)


# ---------- 엔트리 ----------

if __name__ == "__main__":
    debug_on = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("=" * 50)
    print("☕ 오늘의 커피 웹 앱 서버 시작 (SQLite)")
    print("=" * 50)
    print(f"DB: {db.DB_PATH}")
    print("🌐 http://localhost:5000")
    if debug_on:
        print("⚠️  FLASK_DEBUG=1 — 디버거 활성. 운영 환경에서 절대 사용 금지.")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=debug_on)
