#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""메뉴판 ↔ 구글 시트 동기화.

    python scripts/menu_sheet.py push   # JSON → 시트 (시트를 현재 메뉴로 채움)
    python scripts/menu_sheet.py pull   # 시트 → JSON → HTML 재생성

시트에서 원두를 추가·삭제·수정하고 pull 하면 A4 메뉴판이 그대로 다시 나온다.
행 순서가 곧 메뉴판 순서다. 2단 페이지는 위쪽 절반이 왼쪽 단, 아래쪽 절반이 오른쪽 단.

필요한 .env 키: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_SHEETS_REFRESH_TOKEN
  (마지막 키는 `python scripts/google_sheets_auth.py` 로 1회 발급)
페이지 제목·가격 문구·안내문 같은 페이지 설정은 시트가 아니라 JSON 에 남는다.
"""
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "content" / "menu" / "filter-menu.json"
ENV_PATH = ROOT / ".env"

SPREADSHEET_ID = "1aIdaUaNGI-TtugPLEnj47l2wVZOdjx7wJr_bkFUQCK0"
TAB = "메뉴"
HEADERS = ["페이지", "섹션", "원두명", "가공", "컵노트", "가격", "태그"]
API = "https://sheets.googleapis.com/v4/spreadsheets"


def read_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def access_token():
    env = read_env()
    rt = env.get("GOOGLE_SHEETS_REFRESH_TOKEN")
    if not rt:
        sys.exit(
            "[!] .env 에 GOOGLE_SHEETS_REFRESH_TOKEN 이 없다.\n"
            "    먼저 실행: python scripts/google_sheets_auth.py"
        )
    body = urllib.parse.urlencode(
        {
            "client_id": env["GOOGLE_CLIENT_ID"],
            "client_secret": env["GOOGLE_CLIENT_SECRET"],
            "refresh_token": rt,
            "grant_type": "refresh_token",
        }
    ).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", body) as r:
        return json.load(r)["access_token"]


def api(method, path, token, payload=None, params=None):
    url = "%s/%s" % (API, path)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit("[!] Sheets API %s %s\n%s" % (e.code, path, e.read().decode()[:600]))


def ensure_tab(token):
    meta = api("GET", SPREADSHEET_ID, token)
    titles = [s["properties"]["title"] for s in meta["sheets"]]
    if TAB not in titles:
        api(
            "POST",
            "%s:batchUpdate" % SPREADSHEET_ID,
            token,
            {"requests": [{"addSheet": {"properties": {"title": TAB}}}]},
        )
    return meta


def flatten(data):
    rows = [HEADERS]
    for page in data["pages"]:
        for sec in page["sections"]:
            for it in sec["items"]:
                rows.append(
                    [
                        page["key"],
                        sec["heading"],
                        it["name"],
                        it.get("process", ""),
                        it.get("notes", ""),
                        it.get("price", ""),
                        it.get("tag", ""),
                    ]
                )
    return rows


def push():
    token = access_token()
    ensure_tab(token)
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = flatten(data)
    api("POST", "%s/values/%s:clear" % (SPREADSHEET_ID, urllib.parse.quote(TAB)), token, {})
    api(
        "PUT",
        "%s/values/%s" % (SPREADSHEET_ID, urllib.parse.quote("%s!A1" % TAB)),
        token,
        {"values": rows},
        {"valueInputOption": "RAW"},
    )
    # 헤더 굵게 + 고정
    meta = api("GET", SPREADSHEET_ID, token)
    sid = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == TAB)
    api(
        "POST",
        "%s:batchUpdate" % SPREADSHEET_ID,
        token,
        {
            "requests": [
                {
                    "repeatCell": {
                        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {"sheetId": sid, "dimension": "COLUMNS",
                                       "startIndex": 0, "endIndex": len(HEADERS)}
                    }
                },
            ]
        },
    )
    print("[OK] 시트 '%s' 에 %d종 업로드" % (TAB, len(rows) - 1))
    print("     https://docs.google.com/spreadsheets/d/%s/edit" % SPREADSHEET_ID)


def pull():
    token = access_token()
    res = api(
        "GET",
        "%s/values/%s" % (SPREADSHEET_ID, urllib.parse.quote("%s!A1:G500" % TAB)),
        token,
    )
    values = res.get("values", [])
    if not values or values[0][:3] != HEADERS[:3]:
        sys.exit("[!] 시트 '%s' 의 헤더가 예상과 다르다. 먼저 push 로 서식을 맞출 것." % TAB)

    data = json.loads(SRC.read_text(encoding="utf-8"))
    buckets = {}
    for row in values[1:]:
        row = (row + [""] * 7)[:7]
        page_key, heading, name, process, notes, price, tag = [c.strip() for c in row]
        if not name:
            continue
        item = {"name": name}
        if process:
            item["process"] = process
        if tag:
            item["tag"] = tag
        if notes:
            item["notes"] = notes
        if price:
            item["price"] = price
        buckets.setdefault((page_key, heading), []).append(item)

    changed = 0
    for page in data["pages"]:
        for sec in page["sections"]:
            key = (page["key"], sec["heading"])
            if key in buckets:
                if sec["items"] != buckets[key]:
                    changed += 1
                sec["items"] = buckets[key]
            else:
                print("[!] 시트에 '%s / %s' 행이 없다 — JSON 값을 유지한다."
                      % (page["key"], sec["heading"]))

    SRC.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(v) for v in buckets.values())
    print("[OK] 시트 → JSON (%d종, 섹션 %d개 갱신)" % (total, changed))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_menu.py")], check=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "push":
        push()
    elif cmd == "pull":
        pull()
    else:
        sys.exit("사용법: python scripts/menu_sheet.py push|pull")
