# 회원 — 시크릿 원두 카드로 여는 수집 게임

**QR 한 장 = 초대장이자 그 원두의 열쇠다.** 매장에서 필터 커피를 내면서 원두 카드를
건네고, 손님이 그 카드의 QR 을 찍으면

- 처음이면 → 구글 계정으로 가입하면서 **그 원두가 열린다** (첫 번째 열쇠)
- 이미 회원이면 → **그 원두만 열린다**

미션으로 지정한 원두는 열기 전까지 `/beans` 목록에서 자물쇠로 가려진다. 미션이 7종이면
첫 카드를 연 순간 6종이 남는다. 다 열면 마이페이지에 완주 배지가 뜬다.

원두 노트(본인만 보는 감상)는 아직 없다 — 다음 단계다.

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

[Google Cloud Console](https://console.cloud.google.com/) →

1. 프로젝트 생성 (이름 아무거나, 예: `92cafe`)
2. **API 및 서비스 → OAuth 동의 화면**
   - User Type: **외부(External)**
   - 앱 이름 `92도씨 로스터리`, 지원 이메일, 개발자 연락처
   - **승인된 도메인**: `92cafe.co.kr`
   - **개인정보처리방침 URL**: `https://92cafe.co.kr/privacy`
   - 범위(scope)는 `openid`, `email`, `profile` 만. 이 셋은 **비민감(non-sensitive)** 이라
     구글 앱 심사 없이 프로덕션 게시가 된다.
   - 마지막에 **게시(PUBLISH)** 를 눌러 "프로덕션" 상태로 바꾼다.
     테스트 상태로 두면 등록한 테스트 사용자만 로그인된다.
3. **사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **웹 애플리케이션**
   - **승인된 리디렉션 URI**:
     - `https://92cafe.co.kr/auth/google/callback`
     - (로컬 테스트도 할 거면) `http://localhost:8787/auth/google/callback`
   - 만들면 나오는 **클라이언트 ID** 와 **클라이언트 보안 비밀번호**를 복사

### 3. 워커 비밀값

```bash
cd worker
node_modules/.bin/wrangler secret put GOOGLE_CLIENT_ID
node_modules/.bin/wrangler secret put GOOGLE_CLIENT_SECRET
```

`GOOGLE_CLIENT_ID` 가 없으면 로그인 기능 전체가 조용히 꺼진다
(`/api/member/me` 의 `login_enabled: false`, 초대 랜딩은 "준비 중" 안내).

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

1. 같은 탭의 **🎟️ 코드 발급** — 원두를 고르고, 인쇄할 장수(카드 한 장 = 코드 하나), 묶음 이름
2. **🖨️ 카드 인쇄** → `/member-cards`. 원두나 묶음으로 걸러 인쇄한다
3. A4 한 장에 12칸. 카드마다 원두 이름, 컵노트 3개, 고유 QR 이 들어간다
4. 인쇄 설정: 용지 A4 세로, 배율 100%, 여백 없음, **배경 그래픽 켜기**

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

## 다음 단계 (아직 안 만듦)

**원두 노트** — 연 원두에 손님이 **본인만 보는** 감상을 남기는 부분.

- 테이블: `bean_notes`(회원 × 원두, 평점, 본문, 수정일)
- 자리: `/beans/<id>` 상세의 "내 노트" 블록(로그인 + 해금된 사람에게만), `/me` 에서 모아보기
- 공개 여부는 본인만으로 정했다. 나중에 관리자가 골라 공개하는 식으로 넓힐 수 있다.

**완주 보상 운영** — 지금은 마이페이지 배지까지다. 손님이 실제로 모으기 시작한 뒤에
쿠폰 코드 같은 걸 붙이면 된다.
