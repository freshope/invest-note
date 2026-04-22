# Spec: FastAPI analysis routes (summary/behavior/suggestions)

## 배경 / 문제

P1a/P1b/P2(trades + portfolio + 시세)까지 FastAPI 포팅이 완료되어 develop에 merge된 상태.
2단계 백엔드 분리의 마지막 미포팅 영역인 analysis 3 routes(`/api/analysis/summary`, `/behavior`, `/suggestions`)
와 그 의존 라이브러리(aggregate/concentration/profile/rules/period/holding-period)를 FastAPI로
이식해야 Next.js 등가 기능이 완성된다. 배포·컷오버는 이후 별도 spec.

## 목표

- 3개 endpoint가 Next.js와 동일한 응답 구조로 동작한다:
  - `GET /api/analysis/summary?period=1m|3m|6m|ytd|all` → totalTrades/sellTrades/winRate/totalProfitLoss + byStrategy/byEmotion/byTag + 메타지표
  - `GET /api/analysis/behavior?period=...` → profile(5개 score) + inputRates + holdingPeriodDist + positionSizeDist + concentration
  - `GET /api/analysis/suggestions?period=...` → severity 정렬된 Suggestion[] (10개 규칙)
- behavior 라우트: 시세 API 실패 시 costBasis fallback (Next.js 동작 일치).
- 에러 포맷 `{"error": "..."}` 및 401/500 상태 코드 등가.
- pytest(정상/기간 경계/빈 거래/시세 실패/규칙 발동) 통과, ruff clean, 기존 101개 회귀 통과.
- 로컬 uvicorn + curl로 3 endpoint 수동 검증 완료.

## 설계

### 접근 방식

1. **순수 로직 패키지** `domain/analysis/` 신설 — period/holding_period/aggregate/concentration/profile/rules
   를 각각 파일 단위로 분리. TS 원본과 1:1 대응하는 함수 시그니처 유지.
2. **공통 컨텍스트**: `(period, user, pool)` 을 받아 `(all_trades, trades, period)` 를 돌려주는 FastAPI
   `Depends` 헬퍼. `list_trades` 재사용.
3. **라우터 분리**: `routers/analysis.py` 단일 파일에 3 endpoint + behavior 전용 histogram bucket 상수/함수 인라인.
4. **시세 fetch**: behavior 라우트만 `fetch_quotes_by_keys` 호출, 실패 시 `positions0` 유지 (P2 빈 dict 동작 그대로).
5. **JS `Math.round` 일치**: `int(x + 0.5)` (HALF_UP)로 통일해 banker's rounding 차이 제거.
6. **KST 경계**: `zoneinfo.ZoneInfo("Asia/Seoul")` + 수동 `sub_months` — 외부 의존성 추가 없음.
7. **rules.py**: 10개 규칙을 `Callable[[RuleInput], Suggestion | None]` 리스트로 등록 후 severity 정렬.
8. **strategy-adherence.ts 제외**: 라우트 직접 의존 없음 → 이번 스코프 밖.

### 주요 변경 파일

- `api/src/invest_note_api/domain/analysis/__init__.py` — 신규 패키지
- `api/src/invest_note_api/domain/analysis/period.py` — Period/parse_period/filter_by_period (KST)
- `api/src/invest_note_api/domain/analysis/holding_period.py` — compute_holding_days_map
- `api/src/invest_note_api/domain/analysis/aggregate.py` — AnalysisSummary + compute_summary
- `api/src/invest_note_api/domain/analysis/concentration.py` — HHI 상수 + compute_concentration
- `api/src/invest_note_api/domain/analysis/profile.py` — BehaviorProfile + compute_profile
- `api/src/invest_note_api/domain/analysis/rules.py` — 10개 규칙 + evaluate_rules
- `api/src/invest_note_api/routers/analysis.py` — 3 endpoint + bucket 상수
- `api/src/invest_note_api/main.py` — `include_router(analysis.router)` 추가
- `api/tests/test_analysis_logic.py` — 순수 함수 단위 테스트
- `api/tests/test_analysis.py` — 라우터 통합 테스트 (FakePool)
- `api/README.md` — 3 endpoint curl 예시

## 구현 체크리스트

- [ ] `domain/analysis/__init__.py` + `period.py` (parse_period, filter_by_period KST)
- [ ] `domain/analysis/holding_period.py` (compute_holding_days_map)
- [ ] `domain/analysis/concentration.py` (HHI 상수 + compute_concentration)
- [ ] `domain/analysis/aggregate.py` (dataclass + compute_summary + tag 귀속 로직)
- [ ] `domain/analysis/profile.py` (compute_profile + input_rates)
- [ ] `domain/analysis/rules.py` (10 규칙 + evaluate_rules 정렬)
- [ ] `tests/test_analysis_logic.py` (각 순수 함수 단위 테스트, 경계값/빈 거래 포함)
- [ ] `routers/analysis.py` (3 endpoint + bucket 상수/함수)
- [ ] `main.py` 라우터 등록
- [ ] `tests/test_analysis.py` (정상/period 필터/시세 실패 fallback/401)
- [ ] `api/README.md` curl 예시 갱신
- [ ] `poetry run pytest` 전체 통과
- [ ] `poetry run ruff check` 통과
- [ ] 로컬 uvicorn + curl 3 endpoint 검증

## 우려사항 / 리스크

- **`Math.round` HALF_UP vs Python HALF_EVEN**: `int(x + 0.5)` 로 이식. 경계값(`0.5`, `1.5`) 단위 테스트 필수.
- **KST 경계 누락**: `startOfDay` 누락 시 off-by-one. 1m/3m/ytd 경계 날짜 테스트로 검증.
- **빈 거래 edge**: 나누기 0 방지 (aggregate/profile/concentration 모두 TS와 동일하게 방어).
- **Rules 메시지 포맷**: 한글 문자열/단위("%", "일", "HHI 0.53") TS와 완전 동일.
- **FIFO 소수점 오차**: float64 동등 정밀도 — 우려 낮음.
- **strategy-adherence.ts 제외**: 라우트 미사용 → 필요 시 별도 backlog.
