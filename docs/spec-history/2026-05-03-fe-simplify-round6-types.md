# Spec: FE simplify Round 6 — 타입/구조

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md` "FE simplify > 타입/구조 (선택적)" 섹션 2개 항목을 검토·결정한다.

1. `AccountFilter` `"all"` sentinel — 마법 문자열 분기를 type-safe 하게 정리
2. `StockSearchInput` `prevQuery` derived state — useEffect 변경 가치 평가

두 항목 모두 백로그가 "유지/변경 결정 필요" 로 명시한 검토 항목.

## 목표

- **Item 1**: `selectedAccountId` 타입을 `string | null` 로 변경 (`null` = 전체). `ACCOUNT_FILTER_ALL` 상수 제거. UI 동작 동일성 유지.
- **Item 2**: 변경 미진행 결정을 `docs/decisions.md` 에 근거와 함께 기록.
- 타입 체크 + 기존 테스트 통과.

## 설계

### Item 1: AccountFilter `string | null` 마이그레이션

**핵심 결정:** `null` = "전체" sentinel, `string` = account id. `ACCOUNT_FILTER_ALL` 상수 완전 제거.

**근거:**
- API 계층은 sentinel 을 받지 않음 (모두 클라이언트 메모리 필터링) — 백엔드 영향 없음
- `useEffectiveAccountId` 가 이미 정규화 캡슐화하고 있어 컨슈머 변경 비용 낮음
- `string | null` 은 idiomatic TypeScript 패턴, discriminated union 보다 보일러플레이트 적음
- `null` 체크는 TS strictNullChecks 가 강제하므로 단순 `string` 보다 type-safety 향상

**변경 매핑:**

| 현재 | 변경 후 |
|---|---|
| `selectedAccountId === ACCOUNT_FILTER_ALL` | `selectedAccountId === null` |
| `setSelectedAccountId(ACCOUNT_FILTER_ALL)` | `setSelectedAccountId(null)` |
| `value: string` (AccountFilter props) | `value: string \| null` |
| `(value: string) => void` (onChange) | `(value: string \| null) => void` |
| `useEffectiveAccountId(...): string` | `useEffectiveAccountId(...): string \| null` |

**주요 변경 파일 (5개):**

- `app/src/components/providers/AccountFilterProvider.tsx`
  - `ACCOUNT_FILTER_ALL` export 제거
  - `selectedAccountId: string` → `string | null`, 초기값 `null`
  - `useEffectiveAccountId` 반환 타입 → `string | null`, 분기 `=== null`
  - 주석 (line 36-41) 도 새 타입 기준으로 업데이트

- `app/src/components/shared/AccountFilter.tsx`
  - `import { ACCOUNT_FILTER_ALL }` 제거
  - `value: string` → `string | null`, `onChange` 시그니처 동일하게 확장
  - `onChange(ACCOUNT_FILTER_ALL)` (line 27) → `onChange(null)`
  - 활성 비교 `value === ACCOUNT_FILTER_ALL` (line 28) → `value === null`

- `app/src/components/records/TradeList.tsx`
  - import 에서 `ACCOUNT_FILTER_ALL` 제거
  - line 45 `effectiveAccountId === ACCOUNT_FILTER_ALL` → `=== null`

- `app/src/components/stocks/StockDetail.tsx`
  - import 에서 `ACCOUNT_FILTER_ALL` 제거
  - line 38 `effectiveAccountId !== ACCOUNT_FILTER_ALL` → `!== null`

- `app/src/components/panels/DetailPanelProvider.tsx`
  - import 에서 `ACCOUNT_FILTER_ALL` 제거
  - line 211 분기 `=== ACCOUNT_FILTER_ALL` → `=== null`

### Item 2: StockSearchInput 결정 기록 (변경 미진행)

**결정:** 변경 미진행. 현재 "렌더 중 prev state 비교" 패턴 그대로 유지.

**근거 (decisions.md 추가):**
- `StockSearchInput.tsx:51-57` 의 패턴은 React 공식 가이드 ["You Might Not Need an Effect — Adjusting some state when a prop changes"](https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes) 의 권장 패턴 그대로
- **사이클 효율성 차이**: 렌더 중 `if (prev !== current) setPrev(current); setActiveIndex(-1);` 패턴은 첫 commit 전에 React 가 즉시 재렌더로 동기화 → 화면에 stale 한 activeIndex 가 나타나지 않음. 백로그 제안 (`useEffect(() => setActiveIndex(-1), [debouncedValue])`) 는 1) commit → 2) effect 실행 → 3) setState → 4) 재렌더 의 4단계 사이클을 거치므로, 한 프레임 동안 stale activeIndex 가 commit 됨
- 코드 내 기존 주석의 "suggestions 참조 비교 무한루프" 표현은 부정확함 (백로그 제안의 `debouncedValue` 의존성은 string primitive 라 실제 무한루프는 안 남). decisions.md 에는 무한루프 프레이밍이 아니라 **사이클 효율성 / stale frame 회피** 프레이밍으로 기록 — 향후 재제기 방지

## 구현 체크리스트

- [x] `AccountFilterProvider.tsx`: `ACCOUNT_FILTER_ALL` 제거, 타입/초기값/`useEffectiveAccountId` 변경
- [x] `AccountFilter.tsx`: props/onChange 타입 변경, `null` 사용
- [x] `TradeList.tsx`: 분기 `=== null` 변경
- [x] `StockDetail.tsx`: 분기 `=== null` 변경
- [x] `DetailPanelProvider.tsx`: 분기 `=== null` 변경
- [x] 누락된 `ACCOUNT_FILTER_ALL` 참조 grep 재확인 (0개여야 함)
- [x] 타입 체크 통과: `pnpm -C app exec tsc --noEmit`
- [x] 기존 테스트 통과: `pnpm -C app test`
- [x] `docs/decisions.md` 에 Item 1 변경 + Item 2 미진행 결정 기록
- [x] `docs/backlog.md` 에서 두 항목 처리 표시 + Round 6 anchor 추가

## 우려사항 / 리스크

- **localStorage 영속화:** `ACCOUNT_FILTER_ALL` 또는 `selectedAccountId` 영속화 코드는 grep 결과 없음 (메모리 only) → 리스크 없음
- **`useEffectiveAccountId` 반환 null 핸들링:** 현재 모든 호출처가 `=== null` 분기 후 사용하므로 안전. 단일 계좌 전용 API (`portfolioApi.holding`) 사이트는 `useEffectiveAccountId` 를 사용하지 않음 (직접 `accountId: string` 전달)
- **import 누락 잔여:** `ACCOUNT_FILTER_ALL` 을 사용하던 모든 import 제거 후 `tsc` 가 잡아냄. grep 으로 0개 확인

## 검증

1. `pnpm -C app exec tsc --noEmit` — 타입 에러 0
2. `pnpm -C app test` — 기존 테스트 모두 통과
3. `grep -rn "ACCOUNT_FILTER_ALL" app/src` — 0개 매치
4. `grep -rn '<AccountFilter' app/src` — 모든 JSX 호출처가 새 props 시그니처와 호환되는지 확인 (parent 가 string assertion 으로 좁혔던 경우 잡기)
5. `grep -rn '"all"' app/src/components/providers app/src/components/shared app/src/components/records app/src/components/stocks app/src/components/panels` — 손으로 typed literal `"all"` 잔여물 없는지 확인
6. `setSelectedAccountId` 호출처 (TradeList.tsx:29, StockDetail.tsx:36) — 전달 값이 account id (string) 인지 재확인 (변환 필요한 케이스 없는지)
7. 수동 검증 (dev server):
   - 거래 기록 페이지: 전체 → 계좌 A → 전체 토글, 필터링 정상
   - 종목 상세 패널: 계좌 필터 표시 (`isFiltered`) 동작 확인
   - 홈 대시보드: 계좌 칩 토글 → 거래 목록 갱신
