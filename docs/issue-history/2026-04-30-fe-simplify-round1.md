# Spec: FE simplify Round 1 — 안전 중복 제거 + 인라인 헬퍼화

> 완료: 2026-04-30

## 배경 / 문제

`/simplify` 로 FE 전체(`app/src/`, 139 파일 / ~11.4k LOC)를 검토한 결과 약 80 건의 simplify 후보가 도출됐다. 한 번에 모두 손대면 위험·블래스트 반경이 크므로, **BE simplify Tier 3 Round 패턴** 을 따라 위험 낮고 가치 명확한 항목만 Round 1 으로 분리한다.

전수 검토 결과 양호한 측면:
- `any` / `as any` / `@ts-ignore` 0 건
- shadcn ui 직접 import 없음 — `components/base/` 래퍼 규칙 잘 지켜짐
- 도메인 타입 `@/types/database` 단일 소스, API 호출 모두 `api-client.ts` 경유

본 Round 가 다루는 6 개 항목은 모두 단순 추출/치환이며 디자인 결정이 필요 없다.

## 범위 — Round 1 (이번 작업)

1. **`formatTradedAtLabel` 유틸 추출** — `lib/trade-utils.ts` 에 추가, `format(new Date(...), "yyyy년 M월 d일 (EEE)", { locale: ko })` 패턴 4 곳 통합 (`TradeDetail`, `TradeEditPanel`, `TradeBasicForm`, `TradeStrategyResultSection`).
2. **`useClickOutside` 훅 추출** — `hooks/useClickOutside.ts` 신규, `StockSearchInput` / `HoldingSelectInput` 의 `useEffect` 외부클릭 리스너 패턴 통합.
3. ~~**`HoldingCard` pressing state CSS 화**~~ — Round 1 도중 복원. inner note 의 `onPointerDown` `stopPropagation` 으로 outer pressing 을 차단하던 명시적 UX (note 탭 시 outer 카드 scale 안 함) 가 CSS `:active` 로는 보존 불가능 — `:active` 는 stopPropagation 미준수. backlog 로 이관.
4. **중첩 ternary 헬퍼화** —
   - `HoldingSelectInput` placeholder 4 단 ternary → `getPlaceholder()` 함수
   - `SummaryCards` winRateClass 4 단 ternary → `classifyWinRate()` 헬퍼
   - `TradeDetail` 결과 배지(SUCCESS/FAIL/...) 4 분기 → `RESULT_BADGE` 룩업 테이블
5. **`getFirstFormError` 헬퍼** — `Object.values(errors)[0]?.message as string | undefined` 패턴 4 개 폼 통합 (`TradeBasicForm`, `TradeEditPanel`, `TradeMetaBuyForm`, `TradeMetaSellForm`).
6. **`TradeBasicForm:376` 중복 `watch("country_code")` 제거** — 위에서 추출한 `countryCode` 변수 재사용.

## 범위 외 — backlog 로 이관

큰 변경/디자인 결정 필요 항목은 `docs/backlog.md` 에 등록하고 Round 2+ 에서 다룬다:

- **컴포넌트 추출** — `TradeHeaderCard`, `ConfirmDeleteDialog`, `AccountChip`, `TradeTypeBadge`, `EmptyCard`, `BreakdownList`, `ToggleChipGrid`, `ProgressTrack` (Card primitive 30+ 곳)
- **상태/구조 리팩터** — `DetailPanelProvider` 5 중 상태 → `useStaggeredPanel` 훅, `StrategyEmotionFields` `hideEmotion`/`hideStrategy` 분리 사용 정리
- **useEffect 안티패턴** — `TradeBasicForm` commission/tax effect 동기화, `TradeFormPanel` 이중 reset, `ImportTradesPanel` setTimeout reset, `useEnsureValidAccount` effect-setState
- **성능** — recharts dynamic import (`AllocationTabs` / `BehaviorRadar`), `tradesApi.list()` 페이지네이션, `TradeBasicForm` 7 회 `watch()` → `useWatch` 일괄 구독, `TradeCard`/`HoldingCard` `React.memo`, `accountsApi` / `portfolioApi.summary` / `tradesApi` 캐시 키 통일, 무거운 쿼리 staleTime 상향
- **타입 강화** — `AccountFilter` `"all"` sentinel → discriminated union (선택적, 검토 후 결정)

## 구현 체크리스트

- [x] `lib/trade-utils.ts` 에 `formatTradedAtLabel(input: Date | string): string` 추가
- [x] `TradeDetail`, `TradeEditPanel`, `TradeBasicForm`, `TradeStrategyResultSection` 4 곳에서 `formatTradedAtLabel` 사용으로 치환
- [x] `hooks/useClickOutside.ts` 추가
- [x] `StockSearchInput`, `HoldingSelectInput` 의 외부클릭 useEffect 를 `useClickOutside` 로 치환
- [~] `HoldingCard` pressing state CSS 화 — **복원 (보류)**. `:active` 가 inner note 의 stopPropagation 을 미준수해 원본 UX 보존 불가. backlog 로 이관.
- [x] `HoldingSelectInput` placeholder 함수 추출
- [x] `SummaryCards` `classifyWinRate` 헬퍼 추출
- [x] `TradeDetail` `RESULT_BADGE` 룩업 테이블 추출
- [x] `lib/utils.ts` 에 `getFirstFormError(errors)` 헬퍼 추가, 4 개 폼 적용
- [x] `TradeBasicForm:376` `watch("country_code")` → `countryCode` 변수 재사용
- [x] `pnpm -C app exec tsc --noEmit` 그린
- [x] `pnpm -C app test` 그린 (110/110)
- [x] `docs/backlog.md` 에 deferred 항목 추가
- [x] 항목별 1 커밋 (BE round 패턴)

## 우려사항 / 리스크

- 외부클릭 훅 추출 시 `mousedown` vs `pointerdown` 이벤트 차이 — 기존 두 곳 모두 `mousedown` 사용이므로 그대로 유지.
- `formatTradedAtLabel` 의 입력 타입을 `Date | string` 으로 받되 내부에서 `typeof === "string"` 분기. ko locale 의존성은 헬퍼 안으로 흡수.
- HoldingCard 의 `onPress` 와 active scale 조합 — 안드로이드/iOS 의 :active 응답성은 Capacitor 환경에서 검증 필요. 다만 TradeCard 가 동일 패턴을 이미 사용 중이므로 회귀 가능성 낮음.

## 후속 (Round 2 후보)

`docs/backlog.md` 의 deferred 항목 중 위험도·가치 평가 후 다음 5 - 6 개 추출. 우선순위 가정:
1. `ConfirmDeleteDialog` 통합 (DeleteTradeDialog + DeleteAccountDialog) — 텍스트북 수준 중복.
2. `TradeHeaderCard` 추출 — 80 줄 중복 제거.
3. `ToggleChipGrid` — 6 곳 중복, 전략/감정/태그 토글 통합.
4. `TradeBasicForm` `useWatch` 전환 — 입력 지연 즉시 개선.
5. `TradeCard` / `HoldingCard` `React.memo` — 큰 리스트 리렌더 폭증 방지.
