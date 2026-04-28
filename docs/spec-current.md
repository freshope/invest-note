# Spec: 분석 임계값 SOT 통합 (BE 매직 넘버 흡수 + FE 중복 판정 코드 제거)

## 배경 / 문제

분석 임계값은 두 단계로 통합되어 있다. BE SOT(`api/src/invest_note_api/domain/analysis/thresholds.py`, 7개 상수)와 FE SOT(`app/src/lib/constants/analysis.ts`, 동일 7개 상수, `docs/decisions.md` 2026-04-28 정책에 따라 수동 동기화). 그러나 다음 세 형태로 임계값이 여전히 흩어져 있다.

1. **BE 매직 넘버 산재** — `rules.py` 9개 규칙 함수 안에 도메인 판정 임계값(예: `feeling_rate < 40`, `reflection_rate >= 30`, `win_rate < 30`, `missing_tag_rate < 30`, `result_input_rate >= 50`, `avg_holding_days <= 7`)과 최소 샘플 가드(`count < 5`, `result_count < 3`, `sell_trades < 3/5`, `total_trades < 5`)가 직접 박혀 있다.
2. **SOT/FE 동기화 위반** — `app/src/components/analysis/SummaryCards.tsx:37,39`가 `60`/`40`을 하드코드. 오늘(98141ab) `WIN_THRESHOLD`가 60→65로 올라갔지만 SummaryCards는 따라가지 못해 승률 63%면 초록인데 "좋은 승률" 규칙은 발동 안 함 — 정책이 깨졌다는 살아있는 증거.
3. **FE 중복 판정 코드** — `lib/analysis/rules.ts`의 `evaluateRules`는 BE `/api/analysis/suggestions` 응답을 fallback으로 보조(`AnalysisDashboard.tsx:48`). `lib/analysis/strategy-adherence.ts`의 함수는 BE 응답 `byStrategyAdherence`로 이미 대체된 dead code. 둘 다 FE의 임계값 import 의존성을 만들어 SOT 분산을 가중시킨다.

## 목표

- `rules.py`의 모든 비교 숫자 리터럴이 `thresholds.py` 상수로 대체된다 (표시 라벨용 숫자/`_round` 같은 계산 보조 제외).
- `thresholds.py`에 최소 샘플 가드 섹션이 추가되고, `rules.py`가 그것을 import해서 쓴다.
- `SummaryCards.tsx`가 `WIN_THRESHOLD`/`LOSS_THRESHOLD`를 import해서 쓰며, 하드코드된 `60`/`40`이 사라진다.
- `lib/analysis/rules.ts`에서 `evaluateRules` 함수와 임계값 import가 제거되고, `Suggestion` 타입만 남는다 (FE는 BE 응답만 표시).
- `AnalysisDashboard.tsx`의 fallback 호출이 사라진다.
- `lib/analysis/strategy-adherence.ts`가 통째로 삭제되거나, `StrategyEvaluation` 타입만 다른 위치로 이전된다.
- BE/FE 테스트가 모두 통과한다.

## 설계

### 접근 방식

#### 1) BE: `thresholds.py` 확장

다음 두 섹션을 추가하고 `rules.py`가 import한다.

```python
# 도메인 판정 임계값 — rules.py에서 사용
FEELING_RATE_HIGH = 40            # _rule_feeling_heavy: '감/직감' 비율(%)
REFLECTION_RATE_LOW = 30          # _rule_no_reflection: 회고 작성률(%)
LOSING_STRATEGY_RATE = 30         # _rule_losing_strategy: 손실 전략 승률(%)
MISSING_TAG_RATE_HIGH = 30        # _rule_tag_missing: 태그 누락률(%)
RESULT_INPUT_RATE_LOW = 50        # _rule_result_missing/_rule_high_winrate: 결과 입력률(%)
SCALPING_HOLDING_LIMIT_DAYS = 7   # _rule_holding_mismatch: 스캘핑 평균 보유일 한계

# 최소 샘플 가드 — 통계적 신뢰도 확보를 위한 최소 거래/결과 수
MIN_EMOTION_TRADES = 5            # _rule_fomo/_rule_calm: 감정별 최소 거래 수
MIN_EMOTION_RESULTS = 3           # _rule_fomo: 감정별 최소 결과 수
MIN_TOTAL_TRADES = 5              # _rule_feeling_heavy/_rule_tag_missing/_rule_high_winrate
MIN_SELL_TRADES = 3               # _rule_no_reflection/_rule_result_missing
MIN_HIGH_WINRATE_SELL = 5         # _rule_high_winrate
MIN_SCALPING_TRADES = 3           # _rule_holding_mismatch
MIN_STRATEGY_TRADES = 5           # _rule_losing_strategy
MIN_STRATEGY_RESULTS = 3          # _rule_losing_strategy
```

상수 명명은 "어디에 쓰이는가"가 아닌 "무엇을 의미하는가" 기준. 같은 숫자라도 의미가 다르면 별도 상수.

#### 2) FE: 동기화 위반 수정

`SummaryCards.tsx`에 `WIN_THRESHOLD`/`LOSS_THRESHOLD` import 추가, 라인 37·39 비교문 치환.

#### 3) FE: 중복 판정 코드 제거

- `AnalysisDashboard.tsx` — `evaluateRules` import 및 fallback 호출 제거 (BE suggestions 응답이 빈 배열/실패면 빈 인사이트 표시).
- `lib/analysis/rules.ts` — `evaluateRules`/9개 `_rule*` 함수/임계값 import 모두 삭제, `Suggestion`/`SuggestionMetric` 타입만 보존. 파일 상단 주석을 "BE `/api/analysis/suggestions` 응답 타입 정의"로 갱신.
- `lib/analysis/strategy-adherence.ts` — `STRATEGY_THRESHOLDS` import와 런타임 함수 삭제. `StrategyEvaluation` 타입은 외부(`TradeStrategyResultSection.tsx`, `api-client.ts`)에서 type-only import 중이므로 보존(파일에 타입만 남기거나 다른 모듈로 이전 — 파일 상태 보고 결정).
- `__tests__/analysis.test.ts` — `evaluateRules` describe 블록(라인 384~575) 삭제. BE `tests/test_analysis_rules.py` 가 동일 검증을 담당.

### 명시적으로 변경하지 않는 것

- `WinRateBar.tsx`, `DiversificationPanel.tsx`의 FE 임계값 import — UI 색상/라벨 결정용으로 구조적으로 필요. BE→rating 필드 응답화는 사용자가 선택하지 않음.
- `analysis.py` 라우터의 `_HOLDING_BUCKETS`, `_size_bucket` — 표시용 버킷팅. 사용자가 "샘플 가드까지" 범위로 선택해 제외.
- `app/src/lib/constants/analysis.ts`의 기존 7개 상수.

### 주요 변경 파일

- `api/src/invest_note_api/domain/analysis/thresholds.py` — 판정 임계값 6개 + 샘플 가드 8개 추가
- `api/src/invest_note_api/domain/analysis/rules.py` — 9개 규칙 함수의 매직 넘버를 상수로 치환
- `app/src/components/analysis/SummaryCards.tsx` — 하드코드 60/40 → SOT 상수
- `app/src/components/analysis/AnalysisDashboard.tsx` — `evaluateRules` fallback 제거
- `app/src/lib/analysis/rules.ts` — `evaluateRules` 및 임계값 import 제거, 타입만 보존
- `app/src/lib/analysis/strategy-adherence.ts` — 함수 삭제 (타입만 보존 또는 위치 이전)
- `app/src/lib/analysis/__tests__/analysis.test.ts` — `evaluateRules` describe 블록 삭제
- `docs/decisions.md` — 2026-04-28 결정에 "rules.py 매직 넘버 흡수, FE 중복 판정 코드 제거" 후속 항목 추가

## 구현 체크리스트

- [ ] `thresholds.py`에 도메인 판정 임계값 6개 + 샘플 가드 8개 추가
- [ ] `rules.py` import 확장 + 9개 규칙 함수의 비교문 매직 넘버 → 상수 치환
- [ ] `SummaryCards.tsx` 하드코드 60/40 → `WIN_THRESHOLD`/`LOSS_THRESHOLD`
- [ ] `AnalysisDashboard.tsx` `evaluateRules` import 및 fallback 호출 제거
- [ ] `lib/analysis/rules.ts`에서 `evaluateRules`/`_rule*`/임계값 import 삭제, 타입만 보존
- [ ] `lib/analysis/strategy-adherence.ts` 함수 삭제 (타입은 위치 결정 후 처리)
- [ ] `__tests__/analysis.test.ts`의 `evaluateRules` describe 블록 삭제
- [ ] `docs/decisions.md`에 후속 결정 항목 추가
- [ ] BE 테스트 통과 (`cd api && poetry run pytest -q`)
- [ ] FE 타입 체크 통과 (`pnpm -C app exec tsc --noEmit`)
- [ ] FE 테스트 통과 (`pnpm -C app test`)

## 우려사항 / 리스크

- **BE suggestions 응답 실패 시 인사이트가 빈 상태로 표시됨** — 기존 fallback이 사라지는 비용. SOT 통일을 우선시한 결정이며, 응답 실패는 별도 에러 핸들링(`useAnalysisData`)이 담당. `decisions.md`에 명시.
- **FE `strategy-adherence.ts` 타입 위치** — 파일이 타입 외 다른 export를 갖고 있는지 구현 시 확인 후 결정. dead code 정리이므로 리스크 낮음.
- **FE/BE 동기화 책임은 여전히 수동** — 이번 작업으로 분산도가 줄지만 정책(별도 SOT)은 그대로. 정책 변경은 범위 밖.
