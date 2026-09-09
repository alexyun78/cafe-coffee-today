# 회원 — 시크릿 원두 카드로 여는 수집 게임

**QR 한 장 = 초대장이자 그 원두의 열쇠다.** 매장에서 필터 커피를 내면서 원두 카드를
건네고, 손님이 그 카드의 QR 을 찍으면

- 처음이면 → 구글 계정으로 가입하면서 **그 원두가 열린다** (첫 번째 열쇠)
- 이미 회원이면 → **그 원두만 열린다**

미션으로 지정한 원두는 열기 전까지 `/beans` 목록에서 자물쇠로 가려진다. 미션이 7종이면
첫 카드를 연 순간 6종이 남는다. 다 열면 마이페이지에 완주 배지가 뜬다.

맛본 원두에는 날짜 뱃지가 붙고, 그 원두에만 좋아요·중간·싫어요와 감상평을 남길 수 있다.
본인만 보며 관리자만 전체를 모아 본다.

---

## 지금 되는 것

| 경로 | 내용 |
|---|---|
| `/join/<코드>` | 카드 QR 이 오는 곳. 비회원이면 가입 버튼, 회원이면 "이 카드 열기" 버튼 |
| `/login` | 이미 가입한 사람의 로그인. **여기서 가입은 안 된다** |
| `/me` | 마이페이지 — 시크릿 원두 수집 현황, 프로필, 호칭 설정 |
| `/beans` | 원두 목록. 잠긴 미션 원두는 자물쇠 슬롯으로만 보인다 |
| `/privacy` | 개인정보 처리방침 (구글 OAuth 동의 화면 등록에 필요) |
| `/member-cards` | 시크릿 원두 카드 A4 인쇄 시트 (관리자 PIN) |
| 관리자 `👤 회원` 탭 | **시크릿 원두 고르기**, 원두별 카드 발급, 회원 목록, 정지와 복구 |

홈 네비에 로그인 버튼이 있다 — 비로그인이면 `로그인`, 로그인 상태면 `<호칭> 기록`.
가입은 여전히 매장 QR 카드로만 되지만, **이미 가입한 사람은 폰을 바꾸거나 브라우저 기록을
지워도 돌아올 수 있어야 한다.** 계정이 구글에 묶여 있어 로그인만 하면 열어둔 원두
(`bean_unlocks`)가 그대로 따라온다. 콜백에서 `google_sub` 로 기존 회원을 찾으면 카드 없이
로그인시키는 게 그 경로다.

구글 로그인이 아직 설정되지 않았으면(`login_enabled=false`) 버튼을 눌러도 막다른 길이라
링크 자체를 숨긴다. `/beans` 의 잠금 안내에도 같은 조건으로 로그인 링크가 붙는다.

---

## 구조

- **스키마**: [scripts/members_schema.sql](../scripts/members_schema.sql) (`members`, `invite_codes`) +
  [scripts/members_mission_migration.sql](../scripts/members_mission_migration.sql)
  (`bean_missions`, `bean_unlocks`, `invite_codes.bean_id`). 둘 다 멱등이다 —
  마이그레이션의 `ALTER TABLE` 만 두 번째 실행에서 "duplicate column" 을 내는데 그건 무시하면 된다.
- **워커**: [worker/src/members.ts](../worker/src/members.ts) — OAuth, 세션, 초대 코드, 관리자 API.
- **세션**: 관리자와 같은 HMAC 서명 쿠키(`util.signToken`)를 salt 만 바꿔 쓴다(`member-token-v1`).
  D1 에 세션 테이블을 두지 않는다. 쿠키 이름 `mem`, 유효기간 90일.
- **초대 코드**: 32자 알파벳(혼동되는 `I O 0 1` 제외) 10자리 = 약 50비트. 추측으로 맞힐 수 없다.
  표기는 `ABCDE-FGHJK`, 저장은 하이픈 없이. 입력은 소문자와 하이픈도 받아 정규화한다.
  코드마다 `bean_id` 가 붙어 있고, 그게 그 카드가 여는 원두다.

### ⚠️ 잠금이 진짜이려면 — index.json 은 웹에 없다

`/beans` 는 원래 브라우저가 `/static/beans/index.json` 을 직접 받아 그렸다. 그러면 주소창에
그 파일을 치는 것만으로 잠긴 원두가 다 보인다. 그래서

- `.assetsignore` 에 `/static/beans/index.json` 을 넣어 **웹 서빙에서 뺐다**
- Worker 가 [worker/src/beancat.ts](../worker/src/beancat.ts) 에서 그 JSON 을 **번들로 import** 한다
- 카드 데이터는 `/api/beans/cards` 와 `/api/beans/cards/<id>` 로만 나간다.
  잠긴 원두는 목록에 개수(`locked`)로만 실리고, 상세는 **404** 로 떨어진다(존재 자체를 알리지 않는다)

**원두를 추가·수정하는 방법은 그대로 `static/beans/index.json` 편집이다.** 다만 그 파일이 이제
Worker 번들에 들어가므로, 고친 뒤에는 Worker 가 다시 배포돼야 반영된다(푸시하면 자동).
`scripts/build_bean_print.py` 는 로컬 파일을 읽으므로 영향 없다.

### API

| 메서드 | 경로 | 인증 |
|---|---|---|
| GET | `/api/member/me` | 공개 (비로그인이면 `member: null`) |
| PUT | `/api/member/me` | 회원 (호칭 변경) |
| POST | `/api/member/logout` | 공개 |
| GET | `/api/member/invite/<코드>` | 공개 (코드 상태 + 묶인 원두 이름) |
| POST | `/api/member/unlock` | 회원 (로그인 상태에서 카드로 원두 열기) |
| GET | `/api/beans/cards` | 공개 (잠금 반영된 목록) |
| GET | `/api/beans/cards/<id>` | 공개 (잠기면 404) |
| GET | `/auth/google/start` | 공개 → 구글로 리디렉션 |
| GET | `/auth/google/callback` | 구글이 호출 |
| GET | `/api/member/admin/overview` | PIN |
| GET | `/api/member/admin/beans` | PIN (원두 목록 + 미션 여부 + 연 사람 수) |
| PUT | `/api/member/admin/missions` | PIN (시크릿 원두 지정 — 보낸 목록이 곧 미션 세트) |
| GET/POST | `/api/member/admin/invites` | PIN (조회 / 원두별 카드 발급) |
| DELETE | `/api/member/admin/invites/<코드>` | PIN (안 쓴 코드만) |
| PUT | `/api/member/admin/members/<id>` | PIN (정지·복구, 호칭) |

### 흐름

**비회원이 카드를 찍었을 때**

1. `/join/<코드>` → `/api/member/invite/<코드>` 로 코드와 원두를 확인
2. "구글 계정으로 열기" → `/auth/google/start?invite=<코드>`
   서명한 state 쿠키(nonce + 코드 + 돌아갈 경로)를 굽고 구글로 보낸다
3. 콜백 → state 대조 → 인가 코드를 토큰으로 교환 → `id_token` 의 `aud`, `iss`, `exp` 확인
4. `members` INSERT → 코드 소진 → `bean_unlocks` INSERT
5. `/me?welcome=1&unlocked=<원두>` — 마이페이지에서 방금 연 카드를 보여준다

**이미 회원이 카드를 찍었을 때**

1. `/join/<코드>` 가 로그인을 감지 → "🔓 이 카드 열기" 버튼
2. `POST /api/member/unlock {code}` → 코드 소진 + 해금
3. `/beans/<원두>?unlocked=1` — 열린 카드로 바로 보낸다

**규칙 두 개**

- 코드 소진은 조건부 UPDATE(`WHERE redeemed_by IS NULL`) 한 곳이라, 같은 카드를 동시에 써도
  한 명만 성공한다.
- **이미 연 원두의 카드는 소진되지 않는다.** 손님이 그 카드를 다른 사람에게 넘길 수 있게
  일부러 그렇게 했다. 화면도 "이 카드는 아직 쓰이지 않았으니 다른 분께 넘기셔도 됩니다"로 안내한다.

---

## 최초 1회 셋업

### 1. D1 스키마

```bash
cd worker
node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/members_schema.sql
```

### 2. 구글 OAuth 클라이언트 (사장님이 직접)

끝나면 손에 남는 건 문자열 **두 개**다. 그 둘을 3단계에서 워커에 넣으면 로그인이 켜진다.

- **클라이언트 ID** — `1234567890-abcdefg....apps.googleusercontent.com` 처럼 생겼다
- **클라이언트 보안 비밀번호(Client secret)** — `GOCSPX-...` 처럼 생겼다

> ⚠️ **기존 `.env` 의 `GOOGLE_CLIENT_ID` 를 재사용하지 말 것.** 그건 인사이트 인제스트와
> 메뉴 시트가 쓰는 Drive 용이고, `drive` 는 구글이 말하는 **민감 권한**이다. 손님 로그인에
> 얹으면 앱 심사 대상이 되어 버린다. **새 프로젝트, 새 클라이언트**로 만든다.

#### 2-1. 프로젝트 만들기

1. https://console.cloud.google.com 에 매장 구글 계정으로 로그인
2. 화면 맨 위 왼쪽, 로고 옆의 **프로젝트 선택기**를 누른다 → **새 프로젝트**
3. 이름 `92cafe-login` (아무거나) → **만들기**. 30초쯤 걸린다
4. 만들어지면 **프로젝트 선택기에서 그 프로젝트로 전환**한다. (이게 빠지면 다음 단계가
   엉뚱한 프로젝트에 저장된다)

#### 2-2. 동의 화면 (손님에게 보이는 구글 화면)

왼쪽 메뉴 **API 및 서비스 → OAuth 동의 화면**. 최근 콘솔에서는 **Google 인증 플랫폼**
(Google Auth Platform)으로 넘어가고 항목이 `개요 / 브랜딩 / 대상 / 클라이언트 / 데이터 액세스`
로 나뉜다. 둘 중 어느 화면이든 채울 값은 같다.

| 항목 | 넣을 값 |
|---|---|
| User Type / 대상(Audience) | **외부(External)** |
| 앱 이름 | `92도씨 로스터리` — 손님이 로그인할 때 이 이름을 본다 |
| 사용자 지원 이메일 | 매장 구글 계정 |
| 앱 로고 (선택) | 넣으면 브랜드 심사가 붙을 수 있다. **비워두는 쪽을 권한다** |
| 앱 도메인 → 홈페이지 | `https://92cafe.co.kr` |
| 개인정보처리방침 링크 | `https://92cafe.co.kr/privacy` |
| 서비스 약관 링크 | 비워도 된다 |
| 승인된 도메인 | `92cafe.co.kr` |
| 개발자 연락처 이메일 | 매장 구글 계정 |

**범위(Scopes)**: `데이터 액세스` 또는 `범위 추가 또는 삭제`에서 아래 셋만 고른다.

```
openid
.../auth/userinfo.email
.../auth/userinfo.profile
```

이 셋은 **비민감(non-sensitive)** 이라 구글 심사 없이 프로덕션으로 게시된다. 목록에
`drive`, `gmail` 같은 게 섞이면 그때부터 심사 대상이니 **절대 추가하지 말 것**.

#### 2-3. ⚠️ 반드시 "게시" 하기 (제일 많이 빠뜨리는 단계)

동의 화면 **개요** 또는 **대상(Audience)** 에 게시 상태가 있다.

- `테스트(Testing)` 상태면 → **따로 등록한 테스트 사용자 100명만** 로그인된다. 손님은 못 들어온다.
  게다가 이 상태에서는 발급된 토큰이 **7일 만에 만료**된다.
- **`앱 게시` / `PUBLISH APP` 를 눌러 `프로덕션(In production)` 으로 바꾼다.**

확인 문구가 뜨면 확인. 비민감 범위만 쓰므로 심사 요청 화면은 안 나온다.

#### 2-4. 클라이언트 만들기

왼쪽 메뉴 **클라이언트(Clients)** 또는 **API 및 서비스 → 사용자 인증 정보** →
**사용자 인증 정보 만들기 → OAuth 클라이언트 ID**

| 항목 | 넣을 값 |
|---|---|
| 애플리케이션 유형 | **웹 애플리케이션** |
| 이름 | `92cafe web` (내부용, 손님에게 안 보인다) |
| 승인된 자바스크립트 원본 | **비워둔다** (서버끼리 주고받는 방식이라 필요 없다) |
| 승인된 리디렉션 URI | 아래 값 **하나** |

```
https://92cafe.co.kr/auth/google/callback
```

**한 글자도 다르면 안 된다.** 끝에 슬래시(`/`)를 붙이지 말 것. `www.` 를 붙이지 말 것.
`http` 가 아니라 `https` 일 것.

> www 나 http 로 들어온 손님도 워커가 위 주소 하나로 고정해서 구글에 보낸다
> (`worker/src/members.ts` 의 `redirectUri`, `wrangler.jsonc` 의 `SITE_HOST`).
> 그래서 등록할 URI 는 이 하나면 충분하다.

로컬에서도 테스트하고 싶으면 `wrangler dev` 가 찍어주는 주소 그대로 한 줄 더 넣는다
(예: `http://127.0.0.1:8787/auth/google/callback`). **호스트와 포트가 정확히 같아야 한다** —
`localhost` 와 `127.0.0.1` 은 구글에게 서로 다른 값이다. 로컬만 http 가 허용된다.

**만들기** 를 누르면 **클라이언트 ID** 와 **클라이언트 보안 비밀번호**가 뜬다.
창을 닫아도 클라이언트 목록에서 다시 볼 수 있다.

### 3. 워커에 넣기

두 값을 워커의 **비밀값(Secret)** 으로 넣는다. 방법은 둘 중 아무거나.

#### 방법 A — 클라우드플레어 대시보드 (권장, 실수할 여지가 적다)

1. https://dash.cloudflare.com → **Workers & Pages** → **cafe-coffee**
2. **Settings** → **Variables and Secrets**
3. **Add** → Type 을 **Secret** 으로 → 이름 `GOOGLE_CLIENT_ID`, 값 붙여넣기 → **Save**
4. 같은 방법으로 `GOOGLE_CLIENT_SECRET` 하나 더
5. 값 앞뒤에 **공백이나 줄바꿈이 섞이지 않게** 붙여넣는다 (제일 흔한 실수다)

비밀값은 이후 배포에도 그대로 남는다. 코드를 푸시해도 지워지지 않는다.

#### 방법 B — 명령줄 (Git Bash)

```bash
cd /d/python/92/cafe-today-coffee/worker
export CLOUDFLARE_API_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' ../.env | cut -d= -f2- | tr -d '
"')
node_modules/.bin/wrangler secret put GOOGLE_CLIENT_ID       # 물어보면 값 붙여넣고 Enter
node_modules/.bin/wrangler secret put GOOGLE_CLIENT_SECRET
```

`Authentication error` 가 나면 `.env` 의 토큰에 Workers 편집 권한이 없는 것이다.
방법 A 로 넣거나, `node_modules/.bin/wrangler login` 으로 브라우저 로그인을 한 번 하면 된다.

### 3-1. 켜졌는지 확인

```bash
curl -s https://92cafe.co.kr/api/member/me
```

`"login_enabled":true` 가 나오면 끝이다. (비밀값을 넣으면 워커가 알아서 새 값을 쓰므로
따로 배포할 필요 없다. 바로 안 바뀌면 1분쯤 뒤 다시.)

그다음 눈으로 확인할 것:

1. https://92cafe.co.kr 홈 오른쪽 위에 **로그인** 버튼이 나타난다
2. 관리자 `👤 회원` 탭에서 아무 원두로 카드 1장 발급 → `/member-cards` 에서 인쇄나 화면으로 QR 확인
3. 그 QR 을 폰으로 찍어 실제로 가입해 본다 → `/me` 에 그 원두가 뜨면 전 과정이 산 것이다

### 3-2. 안 될 때

| 화면에 뜨는 것 | 원인과 조치 |
|---|---|
| `오류 400: redirect_uri_mismatch` | 리디렉션 URI 오타. 끝 슬래시, `www.`, `http` 를 확인. 구글에 저장한 값과 `https://92cafe.co.kr/auth/google/callback` 이 정확히 같아야 한다 |
| `액세스 차단됨: 이 앱의 요청이 잘못되었습니다` | 대개 같은 원인(리디렉션 URI)이거나 클라이언트 유형이 "웹 애플리케이션"이 아닌 경우 |
| `앱이 차단됨` / 테스트 사용자만 가능 | 동의 화면이 아직 **테스트** 상태다. 2-3 의 게시를 안 했다 |
| `오류 401: invalid_client` | 클라이언트 보안 비밀번호가 틀렸거나 공백이 섞였다. 비밀값을 다시 넣는다 |
| `/login?error=not_configured` | 워커에 `GOOGLE_CLIENT_ID` 가 아직 없다. 이름 철자 확인 |
| `/login?error=token` | 보안 비밀번호 불일치이거나 구글과 통신 실패. 비밀값 재입력 |
| `/login?error=state` | 로그인 시작 후 10분이 지났거나 쿠키가 막혔다. 다시 시도 |
| `/login?error=invite_required` | 가입한 적 없는 계정으로 `/login` 에서 로그인하려 한 것. **정상 동작이다** — 가입은 카드 QR 로만 된다 |

### 4. 개인정보 처리방침 채우기

[static/member/privacy.html](../static/member/privacy.html) 의 `[매장 이메일 주소]` 를
실제 값으로 바꾼다. 구글 심사에서 이 페이지를 본다.

---

## 운영

### 1. 시크릿으로 만들 원두 고르기

관리자 → `👤 회원` 탭 → **🔒 시크릿 원두 (미션)** → "고르기" → 체크 → 저장.
체크한 원두가 그 즉시 `/beans` 에서 자물쇠로 바뀐다. 체크를 풀면 다시 공개된다.
**이미 연 회원의 기록은 그대로 남는다.**

### 2. 카드 만들기

카드는 **두 종류**다. 관리자 `🎟️ 코드 발급` 의 "원두" 칸에서 갈린다.

| 종류 | 원두 칸 | 인쇄물 | QR 을 찍으면 |
|---|---|---|---|
| **원두 카드** | 원두를 고름 | `SECRET CARD` + 원두 이름 + 컵노트 3개 | 가입(처음) 또는 그 원두 해금 |
| **초대 카드** | `(원두 없음 — 가입만)` | `INVITATION` + "회원 초대" | 가입만. 이미 회원이면 "쓰실 필요 없습니다" 안내 |

1. `🎟️ 코드 발급` — 원두(또는 원두 없음), 인쇄할 장수(카드 한 장 = 코드 하나), 묶음 이름
2. `🖨️ 카드 인쇄` → `/member-cards`. 원두별, `(원두 없음 — 초대 전용)`, 묶음으로 걸러 인쇄한다
3. A4 한 장에 12칸, 점선대로 자른다
4. 인쇄 설정: 용지 A4 세로, 배율 100%, 여백 없음, **배경 그래픽 켜기**

> QR 은 [static/member/vendor/qrcode-generator.js](../static/member/vendor/qrcode-generator.js)
> 로 브라우저에서 그린다 (MIT). **CDN 을 쓰지 않는다** — 전에 CDN 주소가 죽어 QR 없는 카드가
> 조용히 인쇄될 뻔했다. 인쇄 전 상단 표시에 `⚠️ QR N개 실패` 가 보이면 인쇄하지 말 것.

안 쓴 코드는 언제든 폐기할 수 있고, 이미 쓰인 코드는 기록으로 남아 폐기되지 않는다.

> `scripts/build_bean_print.py` 가 만드는 `/beans/print.html` 은 **미션 여부를 모른다.**
> 매장 진열용 시트라 시크릿 원두도 그대로 인쇄된다. 손님에게 주는 시크릿 카드는
> `/member-cards` 쪽이다. 진열 시트에서도 빼고 싶으면 그때 스크립트를 손보면 된다.

---

## 알아둘 것

- **APK(Capacitor WebView)에서는 구글 로그인이 막힌다.** 구글이 임베디드 WebView 의
  OAuth 를 차단한다(`disallowed_useragent`). 앱에서도 쓰려면 로그인만 외부 브라우저나
  Custom Tabs 로 띄우도록 APK 를 고쳐야 한다. **아직 안 했다.**
- 세션 쿠키는 `Secure` 라 HTTPS 에서만 붙는다. 프로덕션은 문제없고, 로컬 http 테스트에서
  브라우저 대신 스크립트로 찌를 때는 관리자 Bearer 토큰을 쓰면 된다.
- 구글 프로필(이름, 사진, 이메일)은 **로그인할 때마다 갱신**된다. 손님이 정한 호칭
  (`nickname`)은 덮어쓰지 않는다.
- 정지(`status='정지'`)된 계정은 세션이 있어도 `currentMember` 가 null 을 돌려준다.

---

## 맛본 기록과 감상

QR 을 찍으면 `bean_unlocks` 에 원두와 **찍은 시각**이 남는다. 그게 "맛봤다"는 기록이다.

- `/beans` 목록과 상세에서 내가 맛본 원두에 **☕ 맛봤어요 + 날짜** 뱃지가 붙는다 (본인에게만).
- 상세의 "☕ 내 기록" 블록에서 **좋아요 / 중간 / 싫어요** 와 감상평(최대 2000자)을 남긴다.
- **맛본 원두에만 쓸 수 있다.** `PUT /api/member/notes/<beanId>` 가 `bean_unlocks` 를 확인하고
  없으면 403 을 낸다. 평가와 글을 둘 다 비우고 저장하면 삭제된다.
- **손님끼리는 서로 못 본다.** 조회가 전부 `member_id` 기준이라 남의 기록은 응답에 실리지 않는다.
  관리자만 회원 탭의 `💬 손님 감상`(= `GET /api/member/admin/notes`)으로 전부 본다.
- 마이페이지에 "맛본 원두" 목록이 최근순으로 쌓인다 (평가 이모지, 날짜, 감상 유무).

잠금(미션)과 뱃지는 **별개 축**이다. 미션을 0종으로 두면 원두는 전부 공개인 채로
맛본 것만 뱃지가 붙는다. 몇 종을 시크릿으로 돌리고 싶을 때만 미션을 고르면 된다.

---

## 다음 단계 (아직 안 만듦)

**완주 보상 운영** — 지금은 마이페이지 배지까지다. 손님이 실제로 모으기 시작한 뒤에
쿠폰 코드 같은 걸 붙이면 된다.
