-- 자동 생성: scripts/qgrader_sync.py — 직접 수정하지 말 것
-- 원본: content/qgrader/study-plan.md (version bd08ae9075ad)

DELETE FROM qg_roadmap;
DELETE FROM qg_targets;
DELETE FROM qg_routine_items;
DELETE FROM qg_reference;

INSERT OR REPLACE INTO qg_curriculum (version, source, title, body_md, created_at) VALUES ('bd08ae9075ad', 'content/qgrader/study-plan.md', 'Q 그레이더 6개월 학습·실행 플랜', '# Q 그레이더 6개월 학습·실행 플랜

**2026년 8월 – 2027년 2월 · SP 맞춤 (중급 커퍼 기준, 최소 비용 전략)**

## 먼저 알아야 할 것 — 시험 제도가 바뀌었습니다

참고한 브라운체리 기사는 CQI가 주관하던 구(舊) 체계(22개 모듈) 기준입니다. **2025년 10월 1일부로 Q 그레이더 프로그램은 CQI에서 SCA로 완전히 이관**되었고, 커피가치평가(CVA, Coffee Value Assessment) 체계 기반의 새 프로그램(Evolved Q Grader)으로 개편되었습니다. 기사의 훈련 철학(매일 아로마 30분, 유기산 훈련, 반복 커핑)은 그대로 유효하지만, 시험 구조와 채점 방식은 새 체계에 맞춰 준비해야 합니다.

핵심 변화:

- 주관 기관: CQI → SCA (2025년 10월부터). 국내는 SCA 한국챕터 캘린더에서 일정 확인
- 시험 구성: 기존 19~22개 시험 → **9개 평가(실기 8개 + 필기 55문항)** 로 통합. 과정 중 컴포넌트별 2회 응시 기회
- 평가 틀: SCA 100점 커핑 폼 → **CVA 4개 평가지(물리적·묘사적·정동적·외재적)**. 점수만이 아니라 ''용도에 맞는 추천'' 서술 능력을 평가
- 자격 유지: 3년 유효 동일, 재시험 대신 지속전문개발(CPD) 활동으로 갱신 가능
- 비용: 교육+시험은 트레이너/캠퍼스별 상이(해외 기준 약 $1,650~2,100 + SCA 등록비). 라이선스 발급 비용은 없음

## 1. 새 Q 그레이더 시험 한눈에 보기

| 항목 | 내용 |
|---|---|
| 주관 | SCA (2025.10부터, CVA 기반) |
| 형식 | 6일 연속 집중 교육 + 시험 |
| 평가 | 실기 8개 + 필기 1개(55문항), 총 9개 |
| 재응시 | 과정 중 컴포넌트별 2회 기회, 이후 별도 리테이크 |
| 유효기간 | 3년, CPD 활동으로 갱신 |
| 권장 선수 경험 | 커핑·센서리 실무(중급 이상), CVA 폼 사용 경험, SCA Sensory Skills / Intro to Cupping 권장 |
| 국내 접수 | SCA 한국챕터(korea.sca.coffee) 교육 캘린더 |

### 실기 8개 평가 컴포넌트와 대비 훈련

| 평가 | 내용 | 대비 훈련 |
|---|---|---|
| 후각 식별 (Olfactory) | 아로마 샘플의 카테고리/향 식별 | 아로마 키트 36종 매일 블라인드 |
| 주요 맛 용액 (Main Taste Solutions) | 산·단맛·짠맛 등 기본 맛 종류·강도 식별 | 유기산 4종 + 설탕·소금 희석액 블라인드 |
| 삼각 커핑 (Triangulation) | 3잔 중 다른 1잔 찾기 | 주 1회 이상 삼각 테스트 |
| 묘사적 평가 (Descriptive) | CVA 묘사 평가지로 디스크립터 선택(CATA)·강도 기록 | Flavor Wheel/WCR 렉시콘 언어화 훈련 |
| 정동적 평가 (Affective) | CVA 정동 평가지(9점 척도) 채점, 패널 캘리브레이션 | 커핑 후 9점 채점 → 기준 점수 비교 |
| 물리적 평가 (Green Grading) | 생두 결함 분류·계수 | 생두 300g 결함 분류 연습 |
| 로스팅 문제 (Roasting Problems) | 베이크드·언더디벨롭 등 로스트 결함 컵 식별 | 결함 로스팅 샘플 비교 커핑 |
| 컵 평가 종합 | 블라인드 커핑 종합 평가 | 주 3회 CVA 폼 풀 커핑 |

## 2. 6개월 로드맵 (2026.8 → 2027.2 응시)

| 기간 | 테마 | 핵심 활동 | 월말 목표 |
|---|---|---|---|
| 8월 (M1) | 세팅 & 베이스라인 | 아로마 키트·유기산 구입, CVA 평가지 학습, 첫 블라인드 측정, SCA 한국챕터 일정 확인 | 베이스라인 기록, 아로마 20/36 |
| 9월 (M2) | 후각 집중 | 매일 아침 아로마 30분(오답 향 반복), 향기 노트 언어화, 저녁 유기산 15분 | 아로마 26/36, 유기산 70% |
| 10월 (M3) | 삼각·묘사 | 주 1~2회 삼각 6세트, CVA 묘사 평가지 커핑 기록, 디스크립터 어휘 확장 | 아로마 28/36, 삼각 60% |
| 11월 (M4) | 생두·로스트 결함 | 생두 결함 분류(주 2회, 제한시간), 결함 로스팅 커핑, 필기 이론 정리 | 결함 분류 정확도 80%, 아로마 30/36 |
| 12월 (M5) | 통합 모의 | 주간 모의시험 루틴, 정동 평가 캘리브레이션, 약점 컴포넌트 집중 | 아로마 32/36, 삼각 75%, 모의 필기 80점 |
| 1월 (M6) | 시험 모드 | 실제 응시 환경 재현, 컨디션 관리, 시험 직전 과훈련 금지 | 아로마 33/36 안정 |
| 2월 | 응시 | 6일 과정. 1차는 첫 직감으로, 불합격 컴포넌트만 재응시 | 합격 |

## 3. 일일·주간 훈련 루틴

- **매일 아침 30분** — 아로마 블라인드: 키트를 섞어 무작위로 열고 기록 → 채점 → 틀린 향만 3회 재훈련
- **매일 저녁 15분** — 맛 용액 블라인드: 유기산 4종×3농도 중 5~6개 무작위 시음, 종류·농도 기록. 주 2회는 설탕·소금 포함
- **주 3회** — CVA 풀 커핑: 5잔 프로토콜, 묘사+정동 평가지 작성. 같은 원두를 다른 날 재평가해 편차 확인
- **주 1회** — 삼각 테스트 6세트: 동일 산지 다른 가공 / 로스팅 포인트 차이 샘플. 첫 직감 유지 훈련
- **주 1회** — 생두 결함 분류: 300g, 제한시간, Primary/Secondary 분류·계수
- **주 1회 (M4부터)** — 필기 이론: 가공법·산지·로스팅 화학·CVA 프로토콜 1주제씩

## 4. 준비물 — 최소 비용 전략

| 구분 | 품목 | 접근 |
|---|---|---|
| 필수 | 아로마 키트 | Le Nez du Café 36종(약 50~60만 원). 예산 부담 시 국산 키트로 시작 후 시험 3개월 전 교정 |
| 필수 | 유기산·미각 재료 | 아래 5장 — 합계 3~5만 원 |
| 대체 | 커핑볼 5개+ | 동일한 유리컵·밥공기(200ml 내외)로 대체 가능 |
| 대체 | 커핑 스푼 | 깊은 스테인리스 수프 스푼 |
| 기존 | 저울(0.1g)·그라인더·주전자 | 홈카페 장비 활용, 저울만 0.1g 단위 필수 |
| 소액 | 생두 샘플 | 소분몰에서 커머셜급+스페셜티급 각 1kg 내외 |
| 무료 | CVA 평가지 | SCA 홈페이지에서 무료 다운로드 |

## 5. 미각 훈련용 유기산 구매·희석 가이드

**반드시 ''식품첨가물'' 등급으로 구매. 공업용·시약용 사용 금지.**

| 산 | 형태 | 구매처·검색 키워드 | 예상 가격 |
|---|---|---|---|
| 구연산 (Citric) | 무수 분말 | 쿠팡·네이버 "식품첨가물 구연산" | 1kg 5천~1만 원 |
| 사과산 (Malic) | DL-사과산 분말 | 네이버·식품원료몰(케이준식품원료 등) "DL-사과산 식품첨가물" | 500g~1kg 1~2만 원 |
| 젖산 (Lactic) | 80~90% 액상 | 식품원료몰 "젖산 식품첨가물" | 500ml 1~2만 원 |
| 인산 (Phosphoric) | 75~85% 액상 | 식품원료몰 "인산 식품첨가물" (콜라 산미료 등급). 소량 판매처 적음 — 고객센터에 소분 문의 | 500ml 1~2만 원 |

### 훈련용 희석 레시피 (생수 1L 기준, 저·중·고)

| 산 | 저 | 중 | 고 | 특징 |
|---|---|---|---|---|
| 구연산 | 0.5 g | 1.0 g | 1.5 g | 날카롭게 치고 빠르게 사라짐 (레몬) |
| 사과산 | 0.5 g | 1.0 g | 1.5 g | 부드럽게 퍼지고 길게 지속 (풋사과) |
| 젖산(80%) | 0.6 ml | 1.2 ml | 1.8 ml | 묵직하고 둥글게 깔림 (요거트) |
| 인산(85%) | 0.2 ml | 0.4 ml | 0.6 ml | 드라이·금속성, 뒷맛 짧음 (콜라) |

기본 맛 용액 추가: 설탕 4/8/12 g/L, 소금 0.4/0.7/1.0 g/L

**주의사항**

- 인산 원액은 부식성 — 장갑 착용, 원액 시음 금지, 물에 산을 넣는 순서로 희석
- 희석액은 냉장 보관 후 2~3일 내 사용, 시음은 실온에서
- 입에 머금고 뱉는 방식으로 시음
- 병 바닥에만 라벨을 붙여 셀프 블라인드 가능하게

## 6. 이번 주에 바로 할 일

- [ ] SCA 한국챕터 교육 캘린더에서 2027년 1~3월 과정 일정 확인
- [ ] 아로마 키트 주문 (가장 먼저)
- [ ] 유기산 4종 + 0.1g 저울 + 주사기 주문
- [ ] SCA에서 CVA 평가지 4종 다운로드 후 정독
- [ ] 첫 베이스라인 측정 → 트래커 기록
- [ ] 커핑 스터디에서 캘리브레이션 동료 1~2명 섭외

## 참고 자료

- SCA Q Grader: https://sca.coffee/education/q-grader
- SCA 한국챕터 Q 그레이더: https://korea.sca.coffee/q-grader
- SCA 한국챕터 CVA: https://korea.sca.coffee/education/cva
- Timberline Coffee School, The New Q Grader Program (2026)
- 브라운체리 이명건 대표 합격기 (훈련 루틴 참고)
', '2026-08-08T02:26:33Z');

INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES ('2026-08','M1','8월 (M1)','세팅 & 베이스라인','아로마 키트·유기산 구입, CVA 평가지 학습, 첫 블라인드 측정, SCA 한국챕터 일정 확인','베이스라인 기록, 아로마 20/36',0);
INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES ('2026-09','M2','9월 (M2)','후각 집중','매일 아침 아로마 30분(오답 향 반복), 향기 노트 언어화, 저녁 유기산 15분','아로마 26/36, 유기산 70%',1);
INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES ('2026-10','M3','10월 (M3)','삼각·묘사','주 1~2회 삼각 6세트, CVA 묘사 평가지 커핑 기록, 디스크립터 어휘 확장','아로마 28/36, 삼각 60%',2);
INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES ('2026-11','M4','11월 (M4)','생두·로스트 결함','생두 결함 분류(주 2회, 제한시간), 결함 로스팅 커핑, 필기 이론 정리','결함 분류 정확도 80%, 아로마 30/36',3);
INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES ('2026-12','M5','12월 (M5)','통합 모의','주간 모의시험 루틴, 정동 평가 캘리브레이션, 약점 컴포넌트 집중','아로마 32/36, 삼각 75%, 모의 필기 80점',4);
INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES ('2027-01','M6','1월 (M6)','시험 모드','실제 응시 환경 재현, 컨디션 관리, 시험 직전 과훈련 금지','아로마 33/36 안정',5);
INSERT INTO qg_roadmap (month,label,period,theme,activities,goal,sort_order) VALUES ('2027-02','','2월','응시','6일 과정. 1차는 첫 직감으로, 불합격 컴포넌트만 재응시','합격',6);

INSERT INTO qg_targets (metric,month,value,note) VALUES ('aroma','2026-08',20.0,'베이스라인 기록, 아로마 20/36');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('aroma','2026-09',26.0,'아로마 26/36, 유기산 70%');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('acid','2026-09',70.0,'아로마 26/36, 유기산 70%');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('aroma','2026-10',28.0,'아로마 28/36, 삼각 60%');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('tri','2026-10',3.6,'아로마 28/36, 삼각 60%');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('aroma','2026-11',30.0,'결함 분류 정확도 80%, 아로마 30/36');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('defect','2026-11',80.0,'결함 분류 정확도 80%, 아로마 30/36');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('aroma','2026-12',32.0,'아로마 32/36, 삼각 75%, 모의 필기 80점');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('tri','2026-12',4.5,'아로마 32/36, 삼각 75%, 모의 필기 80점');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('written','2026-12',80.0,'아로마 32/36, 삼각 75%, 모의 필기 80점');
INSERT INTO qg_targets (metric,month,value,note) VALUES ('aroma','2027-01',33.0,'아로마 33/36 안정');

INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (35523412,'아로마 블라인드 (아침 30분)','daily','키트를 섞어 무작위로 열고 기록 → 채점 → 틀린 향만 3회 재훈련',0,1);
INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (253776256,'맛 용액 블라인드 (저녁 15분)','daily','유기산 4종×3농도 중 5~6개 무작위 시음, 종류·농도 기록. 주 2회는 설탕·소금 포함',1,1);
INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (196671759,'CVA 풀 커핑 1회차','weekly','5잔 프로토콜, 묘사+정동 평가지 작성. 같은 원두를 다른 날 재평가해 편차 확인',2,1);
INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (65009390,'CVA 풀 커핑 2회차','weekly','5잔 프로토콜, 묘사+정동 평가지 작성. 같은 원두를 다른 날 재평가해 편차 확인',3,1);
INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (87747808,'CVA 풀 커핑 3회차','weekly','5잔 프로토콜, 묘사+정동 평가지 작성. 같은 원두를 다른 날 재평가해 편차 확인',4,1);
INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (5667505,'삼각 테스트 6세트','weekly','동일 산지 다른 가공 / 로스팅 포인트 차이 샘플. 첫 직감 유지 훈련',5,1);
INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (245017582,'생두 결함 분류','weekly','300g, 제한시간, Primary/Secondary 분류·계수',6,1);
INSERT INTO qg_routine_items (id,label,cadence,detail,sort_order,active) VALUES (28335834,'필기 이론','weekly','가공법·산지·로스팅 화학·CVA 프로토콜 1주제씩',7,1);

INSERT INTO qg_reference (section,sort_order,data) VALUES ('exam',0,'{"항목": "주관", "내용": "SCA (2025.10부터, CVA 기반)"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('exam',1,'{"항목": "형식", "내용": "6일 연속 집중 교육 + 시험"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('exam',2,'{"항목": "평가", "내용": "실기 8개 + 필기 1개(55문항), 총 9개"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('exam',3,'{"항목": "재응시", "내용": "과정 중 컴포넌트별 2회 기회, 이후 별도 리테이크"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('exam',4,'{"항목": "유효기간", "내용": "3년, CPD 활동으로 갱신"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('exam',5,'{"항목": "권장 선수 경험", "내용": "커핑·센서리 실무(중급 이상), CVA 폼 사용 경험, SCA Sensory Skills / Intro to Cupping 권장"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('exam',6,'{"항목": "국내 접수", "내용": "SCA 한국챕터(korea.sca.coffee) 교육 캘린더"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',0,'{"평가": "후각 식별 (Olfactory)", "내용": "아로마 샘플의 카테고리/향 식별", "대비 훈련": "아로마 키트 36종 매일 블라인드"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',1,'{"평가": "주요 맛 용액 (Main Taste Solutions)", "내용": "산·단맛·짠맛 등 기본 맛 종류·강도 식별", "대비 훈련": "유기산 4종 + 설탕·소금 희석액 블라인드"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',2,'{"평가": "삼각 커핑 (Triangulation)", "내용": "3잔 중 다른 1잔 찾기", "대비 훈련": "주 1회 이상 삼각 테스트"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',3,'{"평가": "묘사적 평가 (Descriptive)", "내용": "CVA 묘사 평가지로 디스크립터 선택(CATA)·강도 기록", "대비 훈련": "Flavor Wheel/WCR 렉시콘 언어화 훈련"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',4,'{"평가": "정동적 평가 (Affective)", "내용": "CVA 정동 평가지(9점 척도) 채점, 패널 캘리브레이션", "대비 훈련": "커핑 후 9점 채점 → 기준 점수 비교"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',5,'{"평가": "물리적 평가 (Green Grading)", "내용": "생두 결함 분류·계수", "대비 훈련": "생두 300g 결함 분류 연습"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',6,'{"평가": "로스팅 문제 (Roasting Problems)", "내용": "베이크드·언더디벨롭 등 로스트 결함 컵 식별", "대비 훈련": "결함 로스팅 샘플 비교 커핑"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('components',7,'{"평가": "컵 평가 종합", "내용": "블라인드 커핑 종합 평가", "대비 훈련": "주 3회 CVA 폼 풀 커핑"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('materials',0,'{"구분": "필수", "품목": "아로마 키트", "접근": "Le Nez du Café 36종(약 50~60만 원). 예산 부담 시 국산 키트로 시작 후 시험 3개월 전 교정"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('materials',1,'{"구분": "필수", "품목": "유기산·미각 재료", "접근": "아래 5장 — 합계 3~5만 원"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('materials',2,'{"구분": "대체", "품목": "커핑볼 5개+", "접근": "동일한 유리컵·밥공기(200ml 내외)로 대체 가능"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('materials',3,'{"구분": "대체", "품목": "커핑 스푼", "접근": "깊은 스테인리스 수프 스푼"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('materials',4,'{"구분": "기존", "품목": "저울(0.1g)·그라인더·주전자", "접근": "홈카페 장비 활용, 저울만 0.1g 단위 필수"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('materials',5,'{"구분": "소액", "품목": "생두 샘플", "접근": "소분몰에서 커머셜급+스페셜티급 각 1kg 내외"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('materials',6,'{"구분": "무료", "품목": "CVA 평가지", "접근": "SCA 홈페이지에서 무료 다운로드"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('acids',0,'{"산": "구연산 (Citric)", "형태": "무수 분말", "구매처·검색 키워드": "쿠팡·네이버 \"식품첨가물 구연산\"", "예상 가격": "1kg 5천~1만 원"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('acids',1,'{"산": "사과산 (Malic)", "형태": "DL-사과산 분말", "구매처·검색 키워드": "네이버·식품원료몰(케이준식품원료 등) \"DL-사과산 식품첨가물\"", "예상 가격": "500g~1kg 1~2만 원"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('acids',2,'{"산": "젖산 (Lactic)", "형태": "80~90% 액상", "구매처·검색 키워드": "식품원료몰 \"젖산 식품첨가물\"", "예상 가격": "500ml 1~2만 원"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('acids',3,'{"산": "인산 (Phosphoric)", "형태": "75~85% 액상", "구매처·검색 키워드": "식품원료몰 \"인산 식품첨가물\" (콜라 산미료 등급). 소량 판매처 적음 — 고객센터에 소분 문의", "예상 가격": "500ml 1~2만 원"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('dilution',0,'{"산": "구연산", "저": "0.5 g", "중": "1.0 g", "고": "1.5 g", "특징": "날카롭게 치고 빠르게 사라짐 (레몬)"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('dilution',1,'{"산": "사과산", "저": "0.5 g", "중": "1.0 g", "고": "1.5 g", "특징": "부드럽게 퍼지고 길게 지속 (풋사과)"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('dilution',2,'{"산": "젖산(80%)", "저": "0.6 ml", "중": "1.2 ml", "고": "1.8 ml", "특징": "묵직하고 둥글게 깔림 (요거트)"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('dilution',3,'{"산": "인산(85%)", "저": "0.2 ml", "중": "0.4 ml", "고": "0.6 ml", "특징": "드라이·금속성, 뒷맛 짧음 (콜라)"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('todo',0,'{"task": "SCA 한국챕터 교육 캘린더에서 2027년 1~3월 과정 일정 확인"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('todo',1,'{"task": "아로마 키트 주문 (가장 먼저)"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('todo',2,'{"task": "유기산 4종 + 0.1g 저울 + 주사기 주문"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('todo',3,'{"task": "SCA에서 CVA 평가지 4종 다운로드 후 정독"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('todo',4,'{"task": "첫 베이스라인 측정 → 트래커 기록"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('todo',5,'{"task": "커핑 스터디에서 캘리브레이션 동료 1~2명 섭외"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('links',0,'{"label": "SCA Q Grader", "url": "https://sca.coffee/education/q-grader"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('links',1,'{"label": "SCA 한국챕터 Q 그레이더", "url": "https://korea.sca.coffee/q-grader"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('links',2,'{"label": "SCA 한국챕터 CVA", "url": "https://korea.sca.coffee/education/cva"}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('links',3,'{"label": "Timberline Coffee School, The New Q Grader Program (2026)", "url": ""}');
INSERT INTO qg_reference (section,sort_order,data) VALUES ('links',4,'{"label": "브라운체리 이명건 대표 합격기 (훈련 루틴 참고)", "url": ""}');

INSERT OR IGNORE INTO qg_settings (key,value,updated_at) VALUES ('exam_date','2027-02-01','2026-08-08T02:26:33Z');
