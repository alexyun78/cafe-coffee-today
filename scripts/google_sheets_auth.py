#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""구글 시트 쓰기 권한 토큰 발급 (1회용).

기존 GOOGLE_REFRESH_TOKEN 은 drive.readonly 라 시트에 셀을 쓸 수 없다.
이 스크립트는 같은 OAuth 클라이언트로 spreadsheets 쓰기 스코프를 추가한
refresh token 을 새로 받아 .env 의 GOOGLE_SHEETS_REFRESH_TOKEN 에 저장한다.
(기존 GOOGLE_REFRESH_TOKEN 은 건드리지 않는다 — 서버 인사이트 ingest 가 계속 쓴다.)

실행:
    python scripts/google_sheets_auth.py

브라우저가 열리면 sp.yun 이 아니라 **시트 주인 계정(alexyun@gmail.com)** 으로 로그인할 것.

사전 준비 (1회) — Google Cloud Console → API 및 서비스:
  1) 사용자 인증 정보 → 해당 OAuth 클라이언트 → 승인된 리디렉션 URI 에
     http://localhost:8765/  추가  (클라이언트 유형이 '웹 애플리케이션'일 때만 필요)
  2) 라이브러리 → "Google Sheets API" 사용 설정
"""
import os
import pathlib
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
PORT = 8765
KEY = "GOOGLE_SHEETS_REFRESH_TOKEN"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",  # 기존 ingest 호환
    "https://www.googleapis.com/auth/drive.file",      # 우리가 만든 파일 쓰기
    "https://www.googleapis.com/auth/spreadsheets",    # 시트 셀 읽기/쓰기
]


def read_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def upsert_env(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    env = read_env()
    client_id = env.get("GOOGLE_CLIENT_ID")
    client_secret = env.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("[!] .env 에 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET 이 없다.")
        return 1

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [f"http://localhost:{PORT}/"],
            }
        },
        scopes=SCOPES,
    )

    print(f"브라우저가 열린다. 시트 주인 계정으로 로그인할 것. (리디렉션 http://localhost:{PORT}/)")
    creds = flow.run_local_server(
        port=PORT,
        access_type="offline",
        prompt="consent",
        open_browser=True,
    )

    if not creds.refresh_token:
        print("[!] refresh_token 이 안 왔다. prompt=consent 로 다시 시도할 것.")
        return 1

    upsert_env(KEY, creds.refresh_token)
    print(f"[OK] .env 에 {KEY} 저장 완료.")
    print("     스코프:", " ".join(creds.scopes or SCOPES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
