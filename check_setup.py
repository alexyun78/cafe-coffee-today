#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 커피 - 설정 검증 스크립트
실행 전에 모든 것이 올바르게 설정되었는지 확인합니다.
"""

import sys
import subprocess

def check_python():
    """Python 버전 확인"""
    version = sys.version_info
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("  ⚠️  경고: Python 3.7 이상을 권장합니다.")
        return False
    return True

def check_packages():
    """필요한 패키지 설치 확인"""
    required = ['flask', 'requests', 'flask_cors']
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"✓ {package} 패키지 설치됨")
        except ImportError:
            print(f"✗ {package} 패키지 누락")
            missing.append(package)
    
    if missing:
        print("\n누락된 패키지를 설치하려면 다음 명령어를 실행하세요:")
        print("  pip install -r requirements.txt")
        return False
    return True

def check_notion_config():
    """Notion 설정 확인"""
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Token 확인
        if 'NOTION_TOKEN = ""' in content or 'your_notion_token' in content:
            print("✗ Notion Token이 설정되지 않았습니다")
            print("  app.py 파일에서 NOTION_TOKEN을 설정하세요")
            return False
        else:
            print("✓ Notion Token 설정됨")
        
        # Database ID 확인
        if 'DATABASE_ID = ""' in content or 'your_database_id' in content:
            print("✗ Database ID가 설정되지 않았습니다")
            print("  app.py 파일에서 DATABASE_ID를 설정하세요")
            return False
        else:
            print("✓ Database ID 설정됨")
            
        return True
    except FileNotFoundError:
        print("✗ app.py 파일을 찾을 수 없습니다")
        return False

def check_notion_connection():
    """Notion API 연결 테스트"""
    print("\nNotion API 연결 테스트 중...")
    
    try:
        import requests
        from app import NOTION_TOKEN, DATABASE_ID, headers
        
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        payload = {"page_size": 1}
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✓ Notion API 연결 성공")
            data = response.json()
            print(f"  데이터베이스에서 {len(data.get('results', []))}개 항목을 찾았습니다")
            return True
        elif response.status_code == 401:
            print("✗ Notion API 인증 실패")
            print("  Token이 올바른지 확인하세요")
            return False
        elif response.status_code == 404:
            print("✗ 데이터베이스를 찾을 수 없습니다")
            print("  Database ID가 올바른지 확인하세요")
            return False
        else:
            print(f"✗ Notion API 오류: {response.status_code}")
            print(f"  응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ 연결 테스트 실패: {str(e)}")
        return False

def check_port():
    """포트 5000 사용 가능 여부 확인"""
    import socket
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', 5000))
    sock.close()
    
    if result == 0:
        print("⚠️  포트 5000이 이미 사용 중입니다")
        print("  다른 Flask 서버가 실행 중이거나 다른 프로그램이 포트를 사용하고 있습니다")
        return False
    else:
        print("✓ 포트 5000 사용 가능")
        return True

def main():
    print("=" * 60)
    print("☕ 오늘의 커피 - 설정 검증")
    print("=" * 60)
    print()
    
    results = []
    
    print("[1/5] Python 환경 확인")
    results.append(check_python())
    print()
    
    print("[2/5] 패키지 확인")
    results.append(check_packages())
    print()
    
    print("[3/5] Notion 설정 확인")
    results.append(check_notion_config())
    print()
    
    print("[4/5] 포트 확인")
    results.append(check_port())
    print()
    
    if all(results[:3]):  # Python, 패키지, 설정이 모두 OK면 연결 테스트
        print("[5/5] Notion API 연결 테스트")
        results.append(check_notion_connection())
        print()
    else:
        print("[5/5] Notion API 연결 테스트 건너뜀 (이전 단계 실패)")
        results.append(False)
        print()
    
    print("=" * 60)
    if all(results):
        print("✅ 모든 검사를 통과했습니다!")
        print("\n다음 명령어로 서버를 시작할 수 있습니다:")
        print("  python app.py")
        print("  또는")
        print("  ./start.sh (Linux/Mac)")
        print("  start.bat (Windows)")
    else:
        print("❌ 일부 검사에 실패했습니다.")
        print("\n위의 오류 메시지를 확인하고 문제를 해결한 후 다시 실행하세요.")
        print("자세한 내용은 TROUBLESHOOTING.md 파일을 참조하세요.")
    print("=" * 60)
    
    return 0 if all(results) else 1

if __name__ == '__main__':
    sys.exit(main())
