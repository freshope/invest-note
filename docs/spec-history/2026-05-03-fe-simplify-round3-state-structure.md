# Spec: FE simplify Round 3 — 상태/구조 리팩터

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md`의 "FE simplify Round 1 이후 deferred → 상태/구조 리팩터" 카테고리에 두 항목이 남아 있다.

1. **`StrategyEmotionFields` 강제 분리 사용 정리** — `TradeMetaBuyForm` 이 같은 컴포넌트를 `hideEmotion` / `hideStrategy` 로 두 번 렌더하고 빈 콜백(`() => {}`)을 채워 넣는다. 컴포넌트 이름은 "둘 다"를 암시하지만 호출자는 항상 한 영역만 사용. `StrategyEmotionFields`는 이미 내부적으로 `Label + ToggleChipGrid` 래퍼일 뿐이고, `TradeEditPanel`은 이미 `ToggleChipGrid`를 직접 사용 중이라 패턴이 일관되지 않다.
2. **`HoldingCard` pressing state CSS 화 (재시도)** — Round 1에서 `:active:scale-[0.98]`로 단순화 시도했으나, inner note 영역의 `onPointerDown` `stopPropagation` 이 outer `:active` 전파를 막지 못해 원본 UX (note 탭 시 outer 카드 scale 미발동) 가 깨져 복원되었다 (커밋 `9e494ce`). 사용자 확인 결과 **원본 UX는 의도된 동작**이므로 보존이 필요하다.

## 목표

- `StrategyEmotionFields` 컴포넌트가 코드베이스에서 제거되고, `TradeMetaBuyForm` 이 `ToggleChipGrid` 를 직접 사용한다 (빈 콜백·`hide*` prop 사라짐).
- `HoldingCard` 의 pressing scale 표현이 className 조건부에서 `data-pressing` 속성 + Tailwind data attribute variant로 전환되며, inner note `stopPropagation` 으로 outer pressing이 차단되는 의도된 UX가 그대로 유지된다.
- 타입 체크와 기존 테스트가 모두 통과한다.

## 설계

### 접근 방식

**1. `StrategyEmotionFields` 제거**

- `TradeMetaBuyForm.tsx` (현재 85–110라인의 두 `Controller` + `StrategyEmotionFields` 이중 렌더 블록) 을 다음과 같이 단순화:
  - `Controller` 두 개는 유지하되, render 함수에서 `StrategyEmotionFields` 대신 `Label + ToggleChipGrid` 직접 사용 (TradeEditPanel 252–292라인과 동일 패턴).
  - 빈 콜백, `hideEmotion`, `hideStrategy` 모두 제거.
- `StrategyEmotionFields.tsx` 파일 삭제.
- 다른 사용처 없음 — `TradeEditPanel` 은 이미 `ToggleChipGrid` 직접 사용, 전수 검색 결과 추가 사용처 없음.

**2. `HoldingCard` pressing state — `data-pressing` + Tailwind data variant**

- `useState<boolean>` (`pressing`/`setPressing`) 및 4개 pointer 핸들러 (`onPointerDown/Up/Leave/Cancel`) 는 그대로 유지. 이유: inner note `stopPropagation()` 이 React synthetic event 단계에서 outer `setPressing(true)` 호출 자체를 차단하는 현재 로직이 의도된 UX 의 핵심이며, CSS `:active` 로는 재현 불가.
- className 의 `pressing && "scale-[0.98]"` 조건부 분기 제거.
- 대신 outer `<div>` 에 `data-pressing={pressing ? "true" : undefined}` 추가, className 에 Tailwind 의 arbitrary data variant `data-[pressing=true]:scale-[0.98]` 추가.
- `transition-transform` 등 다른 클래스는 그대로 유지.

> 변화의 의의: pressing 상태를 React 렌더 차원의 className 분기가 아니라 DOM 속성으로 노출함으로써, CSS 가 단일 source of truth 의 시각 변화를 선언적으로 책임진다. JS는 "현재 pressing 인가?" 만 표현. 추후 다른 시각 변화(예: shadow, opacity)를 추가할 때도 className 분기를 늘리지 않고 CSS 만 추가하면 된다.

### 주요 변경 파일

- `app/src/components/records/StrategyEmotionFields.tsx` — **삭제**.
- `app/src/components/records/TradeMetaBuyForm.tsx` — `StrategyEmotionFields` import 제거, 85–110라인 두 Controller 블록을 `Label + ToggleChipGrid` 직접 사용으로 교체. 필요 시 `STRATEGIES` / `EMOTIONS` import 추가 (이미 `STRATEGY_VALUES` / `EMOTION_VALUES` import 중이지만 chip 옵션 배열은 별도).
- `app/src/components/home/HoldingCard.tsx` — outer `<div>` className 의 `pressing && "scale-[0.98]"` 제거, `data-pressing={pressing ? "true" : undefined}` 추가, className 에 `data-[pressing=true]:scale-[0.98]` 추가.

### 재사용 / 참고

- `ToggleChipGrid<T, "">` (`app/src/components/shared/ToggleChipGrid.tsx`) — strategy/emotion 양쪽 모두에서 그대로 사용.
- `STRATEGIES` / `EMOTIONS` 상수 (`app/src/lib/constants/trading.ts`) — TradeMetaBuyForm 에서 이미 import 가능.
- `Label` (`app/src/components/base/Label`) — TradeMetaBuyForm 에서 이미 import 중.
- `TradeEditPanel.tsx` 252–292라인 — 직접 사용 패턴의 참고 구현.

## 구현 체크리스트

- [x] `TradeMetaBuyForm.tsx` 의 두 `StrategyEmotionFields` 호출을 `Label + ToggleChipGrid` 직접 사용으로 교체하고 `StrategyEmotionFields` import 제거 (`STRATEGIES`/`EMOTIONS` import 추가).
- [x] `app/src/components/records/StrategyEmotionFields.tsx` 파일 삭제.
- [x] `HoldingCard.tsx` outer `<div>` 의 className 분기를 `data-pressing` + Tailwind data variant로 교체.
- [x] 수동 검증: 매수 메타 입력 패널에서 전략/감정 칩이 기존과 동일하게 단일 선택되며 react-hook-form 값이 정상 갱신되는지 확인.
- [x] 수동 검증: 보유 종목 카드 탭 시 outer scale 발동, inner note(여러 줄) 영역 탭 시 scale 미발동 — 원본 UX 유지 확인.
- [x] 타입 체크 통과 (`pnpm tsc`).
- [x] 기존 테스트 통과 (`pnpm test`).
- [x] backlog.md 의 "상태/구조 리팩터" 두 항목 체크 / 제거.

## 우려사항 / 리스크

- **HoldingCard data attribute variant 인식** — Tailwind v3.x 의 arbitrary data variant (`data-[pressing=true]:scale-[0.98]`) 가 프로젝트의 Tailwind 설정에서 즉시 동작하는지 확인. 안 되면 `data-pressing="true"` 정확 매칭 대신 `data-[pressing]:` (단순 존재 여부) 또는 `tailwind.config` 의 `safelist` 검토 필요. 단순화 fallback: `data-pressing={pressing || undefined}` + `data-[pressing]:scale-[0.98]`.
- **Round 1 회귀 위험** — Round 1 에서 동일 영역 단순화가 한 번 복원된 이력. 본 spec 은 useState/핸들러를 유지하므로 동일 회귀(=note 탭 시 outer scale 발동)는 발생하지 않아야 한다. 수동 QA 시 멀티라인 note 케이스 반드시 확인.

## 검증 방법

1. `pnpm -C app exec tsc --noEmit` — 타입 체크.
2. `pnpm -C app test` — 기존 테스트 통과.
3. 로컬 개발 서버 (`pnpm -C app dev`) 에서 다음 시나리오 수동 확인:
   - 매수 거래 등록 → 메타 입력 패널 → 전략/감정 칩 단일 선택, 재선택 시 토글 해제, 분석 태그/매수 근거 정상 동작.
   - 홈 화면 보유 종목 카드 → 카드 본체 탭 시 scale-[0.98] 시각 피드백, 손 떼면 복원.
   - 멀티라인 매수 근거가 있는 보유 종목 카드의 note 영역 탭 → outer 카드는 scale 발동하지 않고 note 만 expand/collapse.
   - 단일 라인 note 의 카드 → note 영역 탭 시 expand 안 됨 + outer scale 정상 발동 (현재 동작과 동일).
