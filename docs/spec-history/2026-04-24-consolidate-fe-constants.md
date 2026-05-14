> 완료: 2026-04-24

# Spec: FE Constants 통합 정리 (Phase 2)

## 배경 / 문제

이전 `feature/extract-fe-constants` 작업으로 `app/src/lib/constants/` 폴더가 생성되었지만, 여전히 중복·분산된 상수들이 남아 있다.
가장 큰 문제는 `STRATEGY_LABELS`(3곳), `ADHERENCE_CONFIG`(2곳), `KST`(2곳)의 중복 정의다.
또한 분석 임계치·기간 필터 옵션·거래 라벨 등 공유 가능한 상수들이 컴포넌트/유틸에 흩어져 있어 응집도가 낮다.

## 목표

- `STRATEGY_LABELS`, `ADHERENCE_CONFIG`, `KST`, `COUNTRY_LABELS` 중복이 제거된다.
- 거래 도메인 라벨(`EMOTION_LABELS`, `RESULT_LABELS`, `RESULTS`)이 `constants/trading.ts` 한 곳에서 관리된다.
- 분석 임계치·기본값·기간 필터 옵션이 `constants/analysis.ts` 한 곳에서 관리된다.
- 타임존 상수(`KST`)가 `constants/time.ts`에서 단일 소스로 관리된다.
- 기존 동작이 변경되지 않는다 (순수 리팩토링). 타입체크와 테스트가 통과한다.

## 설계

### 접근 방식

- **새 상수 파일 추가**: `constants/analysis.ts`, `constants/time.ts`
- **기존 상수 파일 확장**: `constants/trading.ts`, `constants/market.ts`
- **import 경로 갱신**: 상수를 사용하던 파일들의 import를 `@/lib/constants/*`로 교체하고, 파일 내부 로컬 정의는 삭제
- 상수 값 자체는 변경하지 않음 (위치만 이동)
- `constants/market.ts`에 이미 있는 `COUNTRY_LABEL`을 `DiversificationPanel`이 직접 import하도록 교체

### 최종 constants 폴더 구조

```
lib/constants/
  analysis.ts     (신규) — HHI_*, TOP1_WEIGHT_HIGH, STRATEGY_THRESHOLDS, WIN/LOSS_THRESHOLD, PERIODS_FULL/COMPACT, DEFAULT_ANALYSIS_PERIOD
  market.ts       (확장) — 기존 + MARKET_LABELS(자산군)
  query.ts        (유지)
  storage.ts      (유지)
  time.ts         (신규) — KST
  trading.ts      (확장) — 기존 + STRATEGY_LABELS, ADHERENCE_CONFIG, EMOTION_LABELS, RESULT_LABELS, RESULTS
  validation.ts   (유지)
```

### 주요 변경 파일

**신규 생성**
- `app/src/lib/constants/analysis.ts`
- `app/src/lib/constants/time.ts`

**확장**
- `app/src/lib/constants/trading.ts`
- `app/src/lib/constants/market.ts`

**import 교체 및 로컬 정의 삭제**
- `app/src/components/records/TradeCard.tsx`
- `app/src/components/records/TradeEditPanel.tsx`
- `app/src/components/records/TradeMetaSellForm.tsx`
- `app/src/components/analysis/DiversificationPanel.tsx`
- `app/src/components/analysis/PeriodFilterTabs.tsx`
- `app/src/components/analysis/WinRateBar.tsx`
- `app/src/lib/analysis/period.ts`
- `app/src/lib/analysis/concentration.ts`
- `app/src/lib/analysis/strategy-adherence.ts`
- `app/src/lib/trade-utils.ts`

## 구현 체크리스트

### 1단계: 중복 제거

- [x] `constants/time.ts` 신규 생성 (`KST`)
- [x] `constants/trading.ts`에 `STRATEGY_LABELS`, `ADHERENCE_CONFIG` 추가
- [x] `TradeCard.tsx` — `STRATEGY_LABELS` 로컬 정의 삭제 + import 교체
- [x] `TradeEditPanel.tsx` — `STRATEGY_LABELS`, `ADHERENCE_CONFIG` 로컬 정의 삭제 + import 교체
- [x] `TradeMetaSellForm.tsx` — `STRATEGY_LABELS`, `ADHERENCE_CONFIG` 로컬 정의 삭제 + import 교체
- [x] `lib/analysis/period.ts` — `KST` 로컬 정의 삭제 + import 교체
- [x] `lib/trade-utils.ts` — `KST` 로컬 정의 삭제 + import 교체
- [x] `DiversificationPanel.tsx` — `COUNTRY_LABELS` 로컬 정의 삭제, `constants/market.ts`의 `COUNTRY_LABEL` 재사용

### 2단계: 도메인 상수 통합

- [x] `constants/trading.ts`에 `EMOTION_LABELS`, `RESULT_LABELS`, `RESULTS` 추가
- [x] `constants/market.ts`에 `MARKET_LABELS`(자산군) 추가
- [x] `constants/analysis.ts` 신규 생성 (`HHI_HIGH`, `HHI_MID`, `TOP1_WEIGHT_HIGH`, `STRATEGY_THRESHOLDS`, `WIN_THRESHOLD`, `LOSS_THRESHOLD`, `PERIODS_FULL`, `PERIODS_COMPACT`, `DEFAULT_ANALYSIS_PERIOD`)
- [x] `TradeCard.tsx` — `EMOTION_LABELS`, `RESULT_LABELS` 로컬 정의 삭제 + import 교체
- [x] `TradeEditPanel.tsx` — `RESULTS` 로컬 정의 삭제 + import 교체
- [x] `DiversificationPanel.tsx` — `MARKET_LABELS` 로컬 정의 삭제 + import 교체
- [x] `PeriodFilterTabs.tsx` — `PERIODS_FULL`, `PERIODS_COMPACT` 로컬 정의 삭제 + import 교체
- [x] `WinRateBar.tsx` — `WIN_THRESHOLD`, `LOSS_THRESHOLD` 로컬 정의 삭제 + import 교체
- [x] `lib/analysis/concentration.ts` — `HHI_*`, `TOP1_WEIGHT_HIGH` 로컬 정의 삭제 + import 교체
- [x] `lib/analysis/strategy-adherence.ts` — `STRATEGY_THRESHOLDS` 로컬 정의 삭제 + import 교체
- [x] `lib/analysis/period.ts` — `DEFAULT_ANALYSIS_PERIOD` 로컬 정의 삭제 + import 교체

### 검증

- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)
- [x] 기존 테스트 통과
- [ ] 상수를 사용하던 화면(분석, 거래 기록, 홈) 수동 확인

## 우려사항 / 리스크

- 순수 리팩토링 — 상수 값 자체는 변경하지 않는다
- `constants/analysis.ts`는 `lib/analysis/*`에 의존하지 않아야 한다 (단방향 유지)
- `lib/analysis/__tests__`가 `HHI_HIGH` 등을 직접 import하는지 확인 후 경로 갱신 필요
