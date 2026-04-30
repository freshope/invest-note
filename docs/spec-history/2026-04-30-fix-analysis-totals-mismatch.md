# Spec: 분석 탭 — 총 실현손익 vs 성과 세션 합계 불일치 해소

> 완료: 2026-04-30

## 배경 / 문제

분석 탭(`/analysis`)에서 "총 실현손익" 카드의 금액과 성과 세션(감정별 / 계획 전략별 / 전략 준수 / 근거 태그별) 항목별 금액 합계가 일치하지 않아 사용자에게 혼란을 준다.

원인 4가지:

### 원인 1 — 화면이 *합계*가 아니라 *평균* PnL을 표시 (핵심)
백엔드 [aggregate.py](api/src/invest_note_api/domain/analysis/aggregate.py)의 `StrategyStats`/`EmotionStats`/`TagStats`/`StrategyAdherenceStats`는 `avg_pnl`만 가진다. 화면도 `item.avgPnL`을 표시한다. 사용자가 "건당 표시 금액"을 합산하면 totalProfitLoss와 절대 일치하지 않는다.

### 원인 2 — `byEmotion`에서 emotion=NULL인 SELL 통째 누락 ([aggregate.py:159-161](api/src/invest_note_api/domain/analysis/aggregate.py:159))
`if t.emotion is None: continue` → 감정 미입력 SELL의 PnL이 합계에서 빠진다.

### 원인 3 — `byTag`에서 reasoning_tags=[] SELL 통째 누락 ([aggregate.py:186-187](api/src/invest_note_api/domain/analysis/aggregate.py:186))
`for tag in sell.reasoning_tags or []:` → 빈 배열이면 어떤 버킷에도 안 들어간다.

### 원인 4 — `byTag`의 다중 태그로 인한 PnL 중복 카운트 (구조적)
한 SELL이 `["TECHNICAL", "NEWS"]`처럼 복수 태그를 가지면 같은 PnL이 두 버킷에 모두 더해진다. 의도된 동작이지만 합계 표시로 바뀌면 차이가 더 명백해진다 → 화면 안내 필요.

### 합계가 이미 일치하는(fallback이 있는) 세션
- `byStrategy` ([aggregate.py:96](api/src/invest_note_api/domain/analysis/aggregate.py:96)): `STRATEGY_UNKNOWN` fallback → "없음" 버킷
- `byStrategyAdherence` ([aggregate.py:126](api/src/invest_note_api/domain/analysis/aggregate.py:126)): `"UNKNOWN"` fallback → "분류 불가" 버킷

## 목표

1. 각 성과 세션이 **합계 PnL** (`sum_pnl`)을 표시 — 평균 표시(`avg_pnl`)는 제거.
2. `byEmotion`/`byTag`에 **"미입력" 버킷** 추가.
3. 결과:
   - `sum(byEmotion.sumPnL) == totalProfitLoss` ✅
   - `sum(byStrategy.sumPnL) == totalProfitLoss` ✅
   - `sum(byStrategyAdherence.sumPnL) == totalProfitLoss` ✅
   - `sum(byTag.sumPnL) ≥ totalProfitLoss` (다중 태그로 인한 중복 — 화면 안내)
4. 메타 지표/행동 분석/제안은 변경되지 않는다.
5. 백엔드 단위 테스트로 위 등식 검증.

## 설계

### 백엔드 dataclass — `avg_pnl` → `sum_pnl` 교체

[aggregate.py](api/src/invest_note_api/domain/analysis/aggregate.py) 4개 dataclass에서 `avg_pnl: float` → `sum_pnl: float` 교체. 계산: `sum(pnls) / len(pnls)` → `sum(pnls)`.

`StrategyStats`의 `avg_holding_days`는 그대로 유지(보유일 평균은 의미가 다름).

### 백엔드 미입력 버킷

[trade_types.py](api/src/invest_note_api/domain/trade_types.py)에 상수:
```python
EMOTION_UNTAGGED = "UNTAGGED"
TAG_UNTAGGED = "UNTAGGED"
```

`byEmotion`: `key = t.emotion or EMOTION_UNTAGGED`
`byTag`: `tags = sell.reasoning_tags or [TAG_UNTAGGED]`

### 응답 직렬화

[routers/analysis.py:89-129](api/src/invest_note_api/routers/analysis.py:89)의 4개 `byXxx` 직렬화에서 `"avgPnL": ... .avg_pnl` → `"sumPnL": ... .sum_pnl`.

### 프론트엔드 타입 + 컴포넌트

- [aggregate.ts](app/src/lib/analysis/aggregate.ts) 4개 인터페이스: `avgPnL` → `sumPnL`
- 4개 컴포넌트: `item.avgPnL` → `item.sumPnL` (표시 형식 그대로)
- [trading.ts](app/src/lib/constants/trading.ts) `EMOTION_LABELS`/`REASONING_TAG_LABELS`에 `UNTAGGED: "미입력"` 추가 (옵션 배열에는 추가 안 함)
- [ReasoningBreakdown.tsx](app/src/components/analysis/ReasoningBreakdown.tsx)에 다중 태그 안내문 1줄 추가

### 주요 변경 파일

- `api/src/invest_note_api/domain/trade_types.py`
- `api/src/invest_note_api/domain/analysis/aggregate.py`
- `api/src/invest_note_api/routers/analysis.py`
- `api/tests/`
- `app/src/lib/analysis/aggregate.ts`
- `app/src/components/analysis/EmotionBreakdown.tsx`
- `app/src/components/analysis/StrategyBreakdown.tsx`
- `app/src/components/analysis/ReasoningBreakdown.tsx`
- `app/src/components/analysis/StrategyAdherencePanel.tsx`
- `app/src/lib/constants/trading.ts`

## 구현 체크리스트

- [x] `trade_types.py`에 `EMOTION_UNTAGGED`, `TAG_UNTAGGED` 상수 추가
- [x] `aggregate.py` 4개 dataclass `avg_pnl` → `sum_pnl`
- [x] `aggregate.py` 4개 집계 블록 `sum(pnls)/len(pnls)` → `sum(pnls)`
- [x] `aggregate.py` `byEmotion` 미입력 fallback
- [x] `aggregate.py` `byTag` 미입력 fallback
- [x] `routers/analysis.py` 응답 키 `avgPnL` → `sumPnL` (4곳)
- [x] `app/src/lib/analysis/aggregate.ts` 4개 인터페이스 `avgPnL` → `sumPnL`
- [x] `EmotionBreakdown.tsx` `avgPnL` → `sumPnL`
- [x] `StrategyBreakdown.tsx` `avgPnL` → `sumPnL`
- [x] `ReasoningBreakdown.tsx` `avgPnL` → `sumPnL` + 다중 태그 안내문
- [x] `StrategyAdherencePanel.tsx` `avgPnL` → `sumPnL`
- [x] `trading.ts` `UNTAGGED: "미입력"` 라벨
- [x] 백엔드 테스트 추가 (미입력 + 합계 등식)
- [x] `cd api && poetry run pytest -q` 통과 (분석 테스트 50/50; 401 인증 테스트 13건은 supabase_url 환경변수 초기화 문제로 우리 변경과 무관)
- [x] `pnpm tsc` 통과
- [ ] 수동 검증

## 검증

1. **백엔드 단위 테스트** — emotion=None과 reasoning_tags=[] 포함 fixture로 `compute_summary`:
   - `byEmotion`/`byTag`에 `"UNTAGGED"` 버킷 존재
   - `sum(e.sum_pnl for e in by_emotion) == total_profit_loss` (epsilon)
   - `sum(s.sum_pnl for s in by_strategy) == total_profit_loss` (epsilon)
   - `sum(s.sum_pnl for s in by_strategy_adherence) == total_profit_loss` (epsilon)
   - 다중 태그 fixture로 `sum(byTag) >= total_profit_loss` 확인
2. **프론트 수동** — 미입력 SELL 포함 계정으로 분석 탭에서 항목 합산 = 총 실현손익 확인 (byTag 제외)

## 우려사항 / 리스크

- 응답 키 `avgPnL` → `sumPnL` breaking change. 분석 탭이 유일 소비처라 동시 변경 안전 (`grep avgPnL`로 확인됨).
- `UNTAGGED` 상수가 폼 옵션에 노출되지 않도록 라벨 객체에만 추가, `EMOTIONS`/`REASONING_TAGS` 옵션 배열은 손대지 않음.
- `byTag`는 다중 태그로 여전히 일치하지 않음 → 안내문으로 보완.
