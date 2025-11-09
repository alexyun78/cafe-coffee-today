import os
import requests
from flask import Flask, jsonify, send_file
from flask_cors import CORS
from datetime import datetime

# .env 파일 로드 (로컬 개발 시)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 프로덕션 환경에서는 python-dotenv가 없을 수 있음
    pass

app = Flask(__name__)
CORS(app)

# 환경 변수에서 읽기 - 기본값 없음 (보안)
NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
DATABASE_ID = os.environ.get('DATABASE_ID')

# 환경 변수가 설정되지 않으면 에러 발생
if not NOTION_TOKEN or NOTION_TOKEN == '':
    raise ValueError(
        "❌ NOTION_TOKEN 환경 변수가 설정되지 않았습니다!\n"
        "로컬 개발: .env 파일에 NOTION_TOKEN을 추가하세요.\n"
        "Render 배포: Environment 설정에서 NOTION_TOKEN을 추가하세요."
    )

if not DATABASE_ID or DATABASE_ID == '':
    raise ValueError(
        "❌ DATABASE_ID 환경 변수가 설정되지 않았습니다!\n"
        "로컬 개발: .env 파일에 DATABASE_ID를 추가하세요.\n"
        "Render 배포: Environment 설정에서 DATABASE_ID를 추가하세요."
    )

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def query_all(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {"page_size": 100}
    results = []
    while True:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
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
        return "".join(r.get("plain_text","") for r in prop["title"]).strip() or None
    if t == "rich_text":
        return "".join(r.get("plain_text","") for r in prop["rich_text"]).strip() or None
    if t == "number":
        return prop["number"]
    if t == "select":
        return prop["select"]["name"] if prop["select"] else None
    if t == "multi_select":
        return [o["name"] for o in prop["multi_select"]]
    if t == "status":
        return prop["status"]["name"] if prop["status"] else None
    if t == "date":
        if not prop["date"]:
            return None
        s = prop["date"]["start"]
        e = prop["date"].get("end")
        return {"start": s, "end": e} if e else {"start": s, "end": None}
    if t in {"created_time","last_edited_time"}:
        return prop[t]
    return None

def flatten_row(page: dict) -> dict:
    """페이지 전체 속성 평탄화"""
    out = {}
    for name, prop in page.get("properties", {}).items():
        out[name] = humanize_property(prop)
    return out

def parse_date(date_obj):
    """날짜 객체를 datetime으로 변환"""
    if not date_obj:
        return None
    if isinstance(date_obj, dict):
        date_str = date_obj.get("start")
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except:
                return None
    return None

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/coffee')
def get_coffee_data():
    try:
        print("API 요청 수신됨")  # 디버깅용 로그
        pages = query_all(DATABASE_ID)
        print(f"총 {len(pages)}개 페이지 로드됨")  # 디버깅용 로그
        
        all_coffee = []
        today_coffee = []
        
        for pg in pages:
            row = flatten_row(pg)
            coffee_data = {
                "커피": row.get("커피"),
                "로스팅": row.get("로스팅"),
                "프로세싱": row.get("프로세싱"),
                "상태": row.get("상태"),
                "컵노트": row.get("컵노트"),
                "감상": row.get("감상"),
                "제공일": row.get("제공일")
            }
            
            all_coffee.append(coffee_data)
            
            # 진행 중인 커피 찾기
            if coffee_data["상태"] == "진행 중":
                today_coffee.append(coffee_data)
        
        print(f"진행 중인 커피: {len(today_coffee)}개")  # 디버깅용 로그
        
        # 정렬: 제공일 최신순 -> 로스팅일 최신순
        def sort_key(item):
            # 제공일 우선
            date_obj = item.get("제공일")
            provide_date = parse_date(date_obj)
            
            # 로스팅일
            roast_obj = item.get("로스팅")
            roast_date = parse_date(roast_obj)
            
            # None은 가장 작은 값으로 처리 (오래된 것)
            provide_time = provide_date.timestamp() if provide_date else 0
            roast_time = roast_date.timestamp() if roast_date else 0
            
            return (-provide_time, -roast_time)
        
        all_coffee.sort(key=sort_key)
        
        return jsonify({
            "success": True,
            "today": today_coffee,
            "history": all_coffee
        })
    except requests.exceptions.RequestException as e:
        print(f"Notion API 오류: {str(e)}")  # 디버깅용 로그
        return jsonify({
            "success": False,
            "error": f"Notion API 연결 오류: {str(e)}"
        }), 500
    except Exception as e:
        print(f"서버 오류: {str(e)}")  # 디버깅용 로그
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    print("=" * 50)
    print("☕ 오늘의 커피 웹 앱 서버 시작")
    print("=" * 50)
    print(f"🌐 접속 주소: http://localhost:5000")
    print(f"📡 API 엔드포인트: http://localhost:5000/api/coffee")
    print(f"🔧 Notion Database ID: {DATABASE_ID}")
    print("=" * 50)
    print("서버를 종료하려면 Ctrl+C를 누르세요\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
