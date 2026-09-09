# 회원 — 시크릿 QR 초대 가입 + 구글 로그인

매장에서 필터 커피를 낼 때 건네는 **시크릿 QR 카드**가 유일한 가입 경로다.
카드를 찍은 사람만 구글 계정으로 가입할 수 있고, 그 뒤로는 코드 없이 로그인한다.

목표는 "미스터리한 콩을 정복하고 피드백을 남기는" 경험이다. 이 문서는 그 1단계
(로그인 뼈대)를 다룬다. 정복 기록과 원두 노트는 2단계에서 붙인다.

---

## 지금 되는 것 (1단계)

| 경로 | 내용 |
|---|---|
| `/join/<코드>` | QR 이 열어주는 초대 랜딩. 코드가 살아 있으면 구글 가입 버튼 |
| `/login` | 이미 가입한 사람의 로그인. **여기서 가입은 안 된다** |
| `/me` | 마이페이지 — 프로필, 호칭 설정, 로그아웃 |
| `/privacy` | 개인정보 처리방침 (구글 OAuth 동의 화면 등록에 필요) |
| `/member-cards` | 초대 카드 A4 인쇄 시트 (관리자 PIN) |
| 관리자 `👤 회원` 탭 | 코드 발급, 회원 목록, 정지·복구 |

홈 네비의 "내 기록" 링크는 **로그인한 사람에게만** 보인다. 비회원에게 로그인 링크를
노출하면 시크릿 카드의 의미가 옅어져서다. 모두에게 보이게 하려면
`static/roastery.html` 의 `nav-member` 처리에서 비로그인 분기를 `/login` 으로 바꾸면 된다.

---

## 구조

- **스키마**: [scripts/members_schema.sql](../scripts/members_schema.sql) — `members`, `invite_codes` 두 개.
  멱등이라 여러 번 돌려도 안전하다.
- **워커**: [worker/src/members.ts](../worker/src/members.ts) — OAuth, 세션, 초대 코드, 관리자 API.
- **세션**: 관리자와 같은 HMAC 서명 쿠키(`util.signToken`)를 salt 만 바꿔 쓴다(`member-token-v1`).
  D1 에 세션 테이블을 두지 않는다. 쿠키 이름 `mem`, 유효기간 90일.
- **초대 코드**: 32자 알파벳(혼동되는 `I O 0 1` 제외) 10자리 = 약 50비트. 추측으로 맞힐 수 없다.
  표기는 `ABCDE-FGHJK`, 저장은 하이픈 없이. 입력은 소문자와 하이픈도 받아 정규화한다.

### API

| 메서드 | 경로 | 인증 |
|---|---|---|
| GET | `/api/member/me` | 공개 (비로그인이면 `member: null`) |
| PUT | `/api/member/me` | 회원 (호칭 변경) |
| POST | `/api/member/logout` | 공개 |
| GET | `/api/member/invite/<코드>` | 공개 (코드 상태만 알려줌) |
| GET | `/auth/google/start` | 공개 → 구글로 리디렉션 |
| GET | `/auth/google/callback` | 구글이 호출 |
| GET | `/api/member/admin/overview` | PIN |
| GET/POST | `/api/member/admin/invites` | PIN (조회 / 발급) |
| DELETE | `/api/member/admin/invites/<코드>` | PIN (안 쓴 코드만) |
| PUT | `/api/member/admin/members/<id>` | PIN (정지·복구, 호칭) |

### 가입 흐름

1. 손님이 카드의 QR 을 찍는다 → `/join/<코드>`
2. 페이지가 `/api/member/invite/<코드>` 로 코드가 살아 있는지 확인한다
3. "구글 계정으로 시작하기" → `/auth/google/start?invite=<코드>`
   서명한 state 쿠키(nonce + 초대코드 + 돌아갈 경로)를 굽고 구글로 보낸다
4. 구글 콜백 → state 대조 → 인가 코드를 토큰으로 교환 → `id_token` 의 `aud`, `iss`, `exp` 확인
5. `members` INSERT → `invite_codes` 를 **조건부 UPDATE 로 소진**
   (`WHERE redeemed_by IS NULL` 이라 같은 코드를 동시에 써도 한 명만 성공한다)
6. 세션 쿠키 발급 → `/me?welcome=1`

이미 가입한 계정이 다시 코드를 들고 와도 **코드는 소진되지 않는다** — 그냥 로그인된다.

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

## 카드 만들기

1. 관리자 → `👤 회원` 탭 → **🎟️ 코드 발급** (개수, 묶음 이름, 유효기간)
2. **🖨️ 카드 인쇄** → `/member-cards` 가 열린다
3. 묶음을 고르고 인쇄 — A4 한 장에 12칸, 점선대로 자르면 카드가 된다
4. 인쇄 설정: 용지 A4 세로, 배율 100%, 여백 없음, **배경 그래픽 켜기**

코드는 발급만 해두고 인쇄는 나중에 해도 된다. 안 쓴 코드는 언제든 폐기할 수 있고,
이미 가입에 쓰인 코드는 기록으로 남아 폐기되지 않는다.

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

## 다음 단계 (2단계 — 아직 안 만듦)

원두별 고정 QR 로 "정복" 스탬프를 찍고, 그 원두에 **본인만 보는** 노트를 남기는 부분.

- 테이블: `bean_stamps`(회원 × 생두, 처음 찍은 날, 횟수), `bean_notes`(회원 × 생두, 평점, 본문)
- 스탬프 QR: `/beans/<id>?stamp=1` 같은 형태. 서버가 **같은 원두 하루 1회**로 제한한다.
  사진을 공유하면 안 마시고도 찍히지만, 성격상 부정행위 방지를 과하게 걸지 않기로 했다.
  나중에 매일 바뀌는 회전 코드로 강화할 수 있다.
- `/me` 의 "정복한 콩" 자리에 40종 그리드. 미정복은 실루엣으로 가려 미스터리를 남긴다.
- 원두 카드(`static/beans/index.json`)의 `green_bean_id` 가 D1 생두와 잇는 키다.
  **카드에 `green_bean_id` 가 빠지면 스탬프도 연결되지 않는다.**
