# Spec: 분석 탭 "거래 결과 입력" → "매수 메모 작성" 교체 + buy_reason 라벨 통일

> 완료: 2026-05-20

## 배경 / 문제

분석 탭 "데이터 입력 품질" 섹션의 **거래 결과 입력**(`result_input_rate`) 항목은 사실상 항상 100%로 표시되어 정보 가치가 없다. `result` 컬럼이 사용자 입력이 아니라 PnL 부호에서 자동 유도되는 값이기 때문이다.

- `be/src/invest_note_api/domain/realized_pnl.py:90` `derive_result_from_pnl(pnl)` — pnl>0→SUCCESS, <0→FAIL, =0→BREAKEVEN.
- `be/src/invest_note_api/db_ops/pnl_sync.py:84` `recalc_group_pnl` — SELL 전수에 `result`를 매번 UPDATE.
- 호출 지점: 거래 CRUD, 브로커 임포트, 데모 시드 — 모든 정상 경로 커버. 매칭 없는 SELL도 수수료/세금으로 pnl<0 → FAIL 부여.
- `trades_repo.py:248`에서 `result`는 `sell_auto_derived=True`로 명시.

사용자가 직접 작성하는 자유 텍스트인 `buy_reason`의 입력률이 더 정직한 "데이터 입력 품질" 지표다. 동시에 거래 입력/표시 UI 전반에서 `buy_reason` 라벨이 "매수 근거"로 되어 있어 같은 패널의 "매수 근거 태그"(`reasoning_tags`)와 의미가 충돌·혼동되므로 "**매수 메모**"로 일괄 통일하여 두 개념(자유 텍스트 메모 vs 태그)을 시각적으로 분리한다.

내부 테스트→심사 단계라 응답 shape 호환은 고려하지 않고 즉시 교체. 단, 분석 탭 데이터 정합성(BE-FE shape, profile, behavior 직렬화)이 깨지지 않게 동시 갱신.

## 목표

1. 분석 응답에서 `result_input_rate` 필드 완전 제거, `ProfileInputRates.buy_reason`(`buyReason`) 신규 필드 추가.
2. `ReviewQualityPanel`에서 "거래 결과 입력" 행 제거 + "매수 메모 작성" 행 추가.
3. `SummaryCards`의 승률 회색 처리 / "입력률 N%" 부제 로직 제거 (자동값 의존이라 의미 없음). `sellTrades === 0`일 때 "-" 표시는 유지.
4. 인사이트 규칙(`rules.py`)에서 `_rule_result_missing` 삭제, `_rule_high_winrate`의 `result_input_rate` 게이트 제거 (sell_trades 충분 조건만 남김).
5. `buy_reason` 표시·입력 화면 8지점의 한국어 라벨을 "매수 근거" → "매수 메모"로 일괄 통일.
6. `buy_reason` 식별자 / `buyReason` camelCase / DB 컬럼명은 **변경하지 않음** (라벨만 변경).
7. BE/FE 타입 체크 + pytest + 분석 탭 수동 검증 통과.

## 설계

### 접근 방식

- BE 도메인 + 스키마에서 `result_input_rate` 일괄 삭제, `ProfileInputRates.result`를 `buy_reason: float`로 교체.
- `buy_reason` 입력률 계산은 `sell_reason`과 동일한 strip 패턴 (`t.buy_reason and t.buy_reason.strip()`).
- FE는 BE-FE 응답 shape 동기화 (CamelModel 자동 변환 → `buyReason`).
- 분석 탭의 result 의존 로직(승률 회색 처리, 부제, 인사이트 규칙) 모두 제거.
- buy_reason 라벨은 식별자는 그대로 두고 한국어 UI 라벨만 일괄 치환.

### 주요 변경 파일

**BE 도메인**
- `be/src/invest_note_api/domain/analysis/aggregate.py` — `AnalysisSummary.result_input_rate` 필드/계산/반환 제거
- `be/src/invest_note_api/domain/analysis/profile.py` — `ProfileInputRates.result` → `buy_reason` 교체 + 계산식 추가
- `be/src/invest_note_api/domain/analysis/rules.py` — `_rule_result_missing` 삭제, `_rule_high_winrate` 게이트 단순화
- `be/src/invest_note_api/domain/analysis/thresholds.py` — `RESULT_INPUT_RATE_LOW` 상수 제거

**BE 스키마**
- `be/src/invest_note_api/schemas/analysis_response.py` — `result_input_rate` 제거, `inputRates.buy_reason` 추가

**BE 테스트**
- `be/tests/test_analysis_logic.py` — `result_input_rate` assert 갱신
- `be/tests/test_analysis.py` — 응답 JSON 필드 검증 갱신

**FE 타입/상수**
- `fe/src/lib/analysis/aggregate.ts` — `resultInputRate` 필드 제거
- `fe/src/lib/analysis/profile.ts` — `result` → `buyReason`
- `fe/src/lib/constants/analysis.ts` — `RESULT_INPUT_RATE_LOW` 제거

**FE 분석 탭 UI**
- `fe/src/components/analysis/SummaryCards.tsx` — `classifyWinRate` 단순화, 부제 제거
- `fe/src/components/analysis/ReviewQualityPanel.tsx` — "거래 결과 입력" 행 제거, "매수 메모 작성" 행 추가
- `fe/src/components/analysis/AnalysisDashboard.tsx` — prop 제거

**FE 라벨 통일 (buy_reason → "매수 메모")**
- `fe/src/components/records/TradeMetaBuyForm.tsx` (label + placeholder)
- `fe/src/components/records/TradeEditPanel.tsx`
- `fe/src/components/records/AutoMetaField.tsx` (label + 빈 상태 메시지)
- `fe/src/components/records/TradeDetail.tsx`
- `fe/src/components/home/HoldingCard.tsx`

## 구현 체크리스트

### A. BE 도메인
- [x] `aggregate.py`: `result_input_rate` 필드/계산/반환 제거
- [x] `profile.py`: `ProfileInputRates.result` → `buy_reason` 교체 및 계산
- [x] `rules.py`: `_rule_result_missing` 삭제 + `_rule_high_winrate` 게이트 단순화
- [x] `thresholds.py`: `RESULT_INPUT_RATE_LOW` 제거

### B. BE 스키마
- [x] `analysis_response.py`: `result_input_rate` 제거, `inputRates.buy_reason` 추가

### C. BE 테스트
- [x] `test_analysis_logic.py`, `test_analysis.py`: assert 갱신
- [x] `cd be && poetry run pytest -q` 통과

### D. FE 타입/상수
- [x] `lib/analysis/aggregate.ts`: `resultInputRate` 제거
- [x] `lib/analysis/profile.ts`: `result` → `buyReason`
- [x] `lib/constants/analysis.ts`: `RESULT_INPUT_RATE_LOW` 제거

### E. FE 분석 탭
- [x] `SummaryCards.tsx`: `classifyWinRate` 단순화 + 부제 제거
- [x] `ReviewQualityPanel.tsx`: "거래 결과 입력" 제거 + "매수 메모 작성" 추가
- [x] `AnalysisDashboard.tsx`: prop 제거

### F. FE 라벨 통일 (buy_reason → "매수 메모")
- [x] `TradeMetaBuyForm.tsx` (label + placeholder)
- [x] `TradeEditPanel.tsx`
- [x] `AutoMetaField.tsx` (label + 빈 상태 메시지)
- [x] `TradeDetail.tsx`
- [x] `HoldingCard.tsx`

### G. 검증
- [x] `pnpm -C fe exec tsc --noEmit` 통과
- [x] `cd be && poetry run pytest -q` 통과
- [x] `pnpm -C fe test` 통과 (FE 테스트 존재 시)
- [x] `grep -rn "resultInputRate\|result_input_rate\|RESULT_INPUT_RATE_LOW" be/src be/tests fe/src` 결과 0
- [x] `grep -rn "매수 근거" fe/src` 결과가 "매수 근거 태그" 외 0
- [x] 수동: 분석 탭 → "데이터 입력 품질"에서 "매수 메모 작성" 표시 + "거래 결과 입력" 사라짐
- [x] 수동: 거래 입력/수정/상세/홀딩 카드에서 "매수 메모" 라벨 통일 확인
- [x] 수동: 승률 카드에 회색 처리/입력률 부제가 사라지고 정상 색상으로 표시

## 우려사항 / 리스크

- `_rule_high_winrate` 게이트 변경 시 sell_trades 충분 가드 외 다른 신뢰도 기준 필요한지 — 우선 단순화로 진행. 실제 데이터로 인사이트 과도 트리거되면 추후 분리.
- `ProfileInputRates.result`를 BehaviorProfile 점수 계산이나 차트 등 다른 곳에서 직접 쓰는지 — 탐색 결과 ReviewQualityPanel 외 직접 사용 없음 (안전).
- "매수 메모"와 "매수 근거 태그" 공존 — 이번 변경의 목적. 자유 텍스트 메모와 선택형 태그를 시각적으로 분리.
- 라벨 누락 방지: 변경 후 `grep -rn "매수 근거" fe/src`가 "매수 근거 태그"만 남도록 확인.
