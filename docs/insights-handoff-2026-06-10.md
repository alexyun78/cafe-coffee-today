# 인사이트 파이프라인 — 작업 인수인계 (2026-06-10 저녁)

다른 PC에서 이어서 작업할 때 이 문서부터 읽는다. 상세 운영 정보는 `CLAUDE.md`
의 "Coffee Insight 자체 생성 파이프라인" 섹션 참조.

## 한 줄 상태

홈페이지 일일 인사이트가 **2026-06-03 이후 정체**. 원인은 십중팔구 **서버에 자체 생성
파이프라인 1회 셋업이 안 됨**(= `.env` 의 `ANTHROPIC_API_KEY` 누락 또는
`cafe-coffee-generate.timer` 미활성). 코드는 repo 에 이미 다 있음.

## 결정사항 (오늘 확정)

- **발행 경로 = 서버 자체 생성**(`scripts/generate_insight.py` + `cafe-coffee-generate.timer`,
  매일 20:30 KST). 서버가 Claude API + 웹검색으로 직접 글 생성 → 렌더 → commit/push.
  **claude.ai 루틴도, Google Drive 도 안 거침.**
- Google Drive 경유(구 방식)는 **폐기 예정 폴백**. OAuth refresh token 7일 만료로
  조용히 멈추는 문제 때문에 더 이상 1차 경로로 쓰지 않는다.
- **토큰 현실**: 생성 단계는 Claude **API(유료) 토큰**을 매일 소모(렌더·인제스트는 0).
  진짜 토큰 0 을 원하면 "백로그 미리 생성 후 하루 1편 릴리스" 방식으로 가야 함 — 미결정.

## 오늘 한 일

- `CLAUDE.md` 보강: 자체 생성 섹션에 ⓐ 운영 현황·인수인계 블록, ⓑ 토큰 현실,
  ⓒ 정체 원인, ⓓ 다른 PC 작업 순서, ⓔ "✅ 살아있는지 검증" 체크리스트 추가.
- (폐기) "Drive 제거 → git 큐 폴더" 접근을 시도했으나, 원격에 이미 더 나은 자체 생성
  파이프라인이 있어 **중복·충돌로 폐기**. `git reset --hard origin/main` 으로 되돌림.
  원격엔 반영 안 됨(잃은 것 없음).

## ⏳ 다음 PC에서 할 일 (순서대로)

1. `git pull` 로 최신 받기. (오늘 `CLAUDE.md` doc 커밋이 푸시됐는지 먼저 확인 —
   안 됐으면 이 PC에서 `git add CLAUDE.md docs/insights-handoff-2026-06-10.md` →
   commit → push.)
2. **서버 상태 검증** (SSH 후). SSH 정보는 `.env` 의 `HOST`/`ID`/`PASSWORD` 참조:
   ```bash
   cd /root/92cafe/cafe-today-coffee
   systemctl is-enabled cafe-coffee-generate.timer          # enabled 여야 정상
   systemctl list-timers 'cafe-coffee-*' --all              # 다음 실행 시각 확인
   grep -q '^ANTHROPIC_API_KEY=' .env && echo "API키 있음" || echo "API키 없음(셋업 필요)"
   grep -q '^INGEST_GITHUB_TOKEN=' .env && echo "push토큰 있음" || echo "push토큰 없음"
   journalctl -u cafe-coffee-generate.service -n 120 --no-pager
   ```
3. **미설정이면 서버 1회 셋업** (CLAUDE.md "서버 최초 1회 셋업" 블록 그대로):
   ```bash
   cd /root/92cafe/cafe-today-coffee
   echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env && chmod 600 .env
   .venv/bin/pip install jinja2==3.1.4 anthropic
   cp systemd/cafe-coffee-generate.service systemd/cafe-coffee-generate.timer /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable --now cafe-coffee-generate.timer
   systemctl start cafe-coffee-generate.service   # 즉시 1편 생성(따라잡기, 멱등)
   journalctl -u cafe-coffee-generate.service -n 80 --no-pager
   ```
4. **사이트 반영 확인**: 생성 성공 → push → ~60초 내 deploy 타이머가 pull+restart.
   ```bash
   curl -s http://49.247.207.115:3002/api/insights | head
   ```
5. (정상 확인 후) claude.ai 루틴 2개(coffee-daily·coffee-trivia)와 Drive 폴백은
   중복 발행 방지를 위해 비활성/정리 검토.

## 빠른 점검 (로컬, 토큰 0)

```bash
# 최신 발행일 — 오늘과 차이 크면 아직 정체
python -c "import json;d=json.load(open('static/insights/index.json'));print('최신:',d['items'][0]['date'],'| 총',len(d['items']),'건')"
```

## 미결 / 다음에 결정할 것

- 토큰 0 백로그 릴리스 방식으로 갈지 여부 (가면 별도 설계 필요).
- 자체 생성 정상화 확인 후 `.env` 의 `GOOGLE_*` 키 및 GitHub Secrets 정리.
