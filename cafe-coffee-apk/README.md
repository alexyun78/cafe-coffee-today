# cafe-coffee-apk

**오늘의 커피** 안드로이드 APK 래퍼 (Capacitor).

## 전략

- `capacitor.config.json`의 `server.url`이 `http://49.247.207.115:3002`를 가리킨다.
- APK는 네이티브 WebView를 띄우고 이 URL을 로드한다. 데이터는 항상 서버 최신.
- `www/index.html`은 폴백 스플래시(서버 불가 시 잠깐 보임).
- **로컬에 Android Studio/SDK 설치 불필요.** APK는 GitHub Actions가 빌드한다.

이 구조는 `D:/python/92cafe_pick/pick-apk` 패턴을 따른 것이다. 차이는 pick은 오프라인 로컬스토리지를 쓰고, coffee는 서버 URL을 로드한다는 점뿐.

## 파일

| 파일 | 역할 |
|---|---|
| `capacitor.config.json` | 앱 ID, 앱 이름, server.url |
| `package.json` | Capacitor 의존성 |
| `www/index.html` | 폴백 스플래시 |
| `www/version.json` | 버전 메타 |
| `.gitignore` | `node_modules/`, `android/`, `dist/` 제외 |

`android/` 디렉토리는 **커밋되지 않는다**. CI가 매 빌드마다 `npx cap add android`로 다시 생성한다.

## 버전 올리기 → 배포

1. `www/version.json`의 `version` 증가 (예: `1.0.0` → `1.0.1`)
2. `git add www/version.json && git commit -m "apk: bump 1.0.1"`
3. `git push`
4. GitHub Actions의 `Build APK` 워크플로가 자동 실행
5. 1~3분 후 서버의 `/root/92cafe/cafe-today-coffee/static/downloads/` 에 배포됨
6. `http://49.247.207.115:3002/apk` 에서 설치 링크

## GitHub Secrets

CI가 서버에 SCP하려면 `SERVER_SSH_KEY` + `SERVER_SSH_KNOWN_HOST` 시크릿이 필요. 설정 방법은 [../scripts/README.md](../scripts/README.md) 참고.

## 로컬 빌드가 꼭 필요하다면

Android Studio 없이도 JDK 17 + Android SDK command-line-tools만으로 가능. 하지만 권장하지 않는다. CI가 더 빠르고 재현 가능하다.
