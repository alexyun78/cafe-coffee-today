"""오늘의 커피 — Flask 백엔드 (SQLite + PIN 관리자).

공개 엔드포인트는 GET /, GET /api/coffee, GET /apk.
관리 엔드포인트는 세션 기반 PIN 인증 필요.
"""
import io
import os
import re
from datetime import date
from functools import wraps

from flask import (
    Flask,
    jsonify,
    request,
    send_file,
    send_from_directory,
    session,
)
from flask_cors import CORS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db

ADMIN_PIN = os.environ.get("ADMIN_PIN", "")
FLASK_SECRET = os.environ.get("FLASK_SECRET", "dev-secret-change-me")

if not ADMIN_PIN:
    raise ValueError(
        "❌ ADMIN_PIN 환경 변수가 설정되지 않았습니다. .env에 ADMIN_PIN을 추가하세요."
    )

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = FLASK_SECRET
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
CORS(app, supports_credentials=True)

db.init_schema()


# ---------- 인증 ----------

def require_pin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"success": False, "error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


@app.post("/api/admin/verify")
def admin_verify():
    data = request.get_json(silent=True) or {}
    pin = (data.get("pin") or "").strip()
    if pin and pin == ADMIN_PIN:
        session["admin"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "invalid pin"}), 401


@app.post("/api/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return jsonify({"success": True})


@app.get("/api/admin/status")
def admin_status():
    return jsonify({"success": True, "authenticated": bool(session.get("admin"))})


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
    return send_file("index.html")


@app.get("/admin")
def admin_page():
    return send_from_directory("static", "admin.html")


@app.get("/apk")
def apk_page():
    return send_from_directory("static", "apk.html")


@app.get("/game")
def game_page():
    return send_from_directory("static", "game.html")


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
    print("=" * 50)
    print("☕ 오늘의 커피 웹 앱 서버 시작 (SQLite)")
    print("=" * 50)
    print(f"DB: {db.DB_PATH}")
    print("🌐 http://localhost:5000")
    print("🔒 관리: http://localhost:5000/admin")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
