# Spec: FE simplify Round 2 — 컴포넌트 추출 (중복 제거)

## 배경 / 문제

Round 1 (`docs/spec-history/2026-04-30-fe-simplify-round1.md`)에서 안전한 헬퍼 추출/인라인 정리만 처리하고, 큰 변경/디자인 결정이 필요한 **컴포넌트 추출** 9 개 항목은 `docs/backlog.md` 의 "FE simplify Round 1 이후 deferred" 섹션으로 이관했다.

이번 Round 2 는 그 중 Round 1 spec 의 후속 우선순위 1-3 번에 명시된 항목만 처리한다 — 코드 탐색으로 중복 패턴이 검증되었고 디자인 결정이 필요 없는 단순 추출이다. 9 개 전체를 한 번에 처리하지 않는 이유: blast radius 관리 + Round 1 패턴 (1 항목 = 1 커밋) 유지.

**기대 효과:** 트레이드 헤더 마크업 80 줄 중복 제거, 토글 그리드 6 곳 일원화, 삭제 다이얼로그 셸 통합. 향후 디자인 변경 (예: 색상 토큰 변경) 시 단일 지점만 수정.

## 목표

1. `DeleteTradeDialog` ↔ `DeleteAccountDialog` → `ConfirmDeleteDialog` 단일 컴포넌트로 통합. 두 호출부 동일 동작 유지.
2. `TradeDetail` ↔ `TradeEditPanel` 의 종목 헤더 카드 마크업 → `TradeHeaderCard` 컴포넌트 추출. 기존 UX (interactive stock link, live form total) 유지.
3. `StrategyEmotionFields` / `TradeEditPanel` / `TradeMetaBuyForm` 의 토글 칩 그리드 6 곳 → 제네릭 `ToggleChipGrid<T>` 로 통합. single/multi 모드, 2/3/4 컬럼 지원.
4. `pnpm -C app exec tsc --noEmit` 그린, `pnpm -C app test` 그린, 회귀 없음.

## 설계

### 접근 방식

Round 1 패턴 답습. 항목별 별도 커밋, 각 커밋은 독립 revert 가능. 새 컴포넌트는 `src/components/shared/` 에 배치.

**1. `ConfirmDeleteDialog` (`shared/ConfirmDeleteDialog.tsx`)**

호출부에 mutation 로직 주입. `pending`/`error` 상태는 호출부가 관리.

```tsx
type ConfirmDeleteDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  pending: boolean;
  error: string | null;
  onConfirm: () => Promise<void> | void;
  confirmLabel?: string; // default "삭제"
  pendingLabel?: string; // default "삭제 중..."
};
```

**2. `TradeHeaderCard` (`records/TradeHeaderCard.tsx`)**

records 도메인 전용. interactive 종목명 (TradeDetail) vs 정적 (TradeEditPanel) 차이는 props 흡수.

```tsx
type TradeHeaderCardProps = {
  trade: Trade;
  isBuy: boolean;
  totalAmount: number;
  price: number;
  quantity: number;
  onStockPress?: () => void;
  stockHref?: string;
};
```

분기: `onStockPress && hasStock` → button / `stockHref` → Link / 그 외 → span.

**3. `ToggleChipGrid<T>` (`shared/ToggleChipGrid.tsx`)**

discriminated union 으로 single/multi 분기:

```tsx
type SingleProps<T extends string> = {
  options: { value: T; label: string }[];
  multi?: false;
  value: T | null | "";
  onChange: (value: T | null) => void;
  columns: 2 | 3 | 4;
  emptyValue?: null | "";
};

type MultiProps<T extends string> = {
  options: { value: T; label: string }[];
  multi: true;
  value: T[];
  onChange: (value: T[]) => void;
  columns: 2 | 3 | 4;
};
```

### 주요 변경 파일

**1. ConfirmDeleteDialog**
- `app/src/components/shared/ConfirmDeleteDialog.tsx` — 신규
- `app/src/components/records/DeleteTradeDialog.tsx` — 제거
- `app/src/components/settings/DeleteAccountDialog.tsx` — 제거
- `app/src/components/records/TradeDetail.tsx` — 호출부 치환
- `app/src/components/settings/AccountCard.tsx` — 호출부 치환

**2. TradeHeaderCard**
- `app/src/components/records/TradeHeaderCard.tsx` — 신규
- `app/src/components/records/TradeDetail.tsx:117-181` — 치환
- `app/src/components/records/TradeEditPanel.tsx:168-207` — 치환

**3. ToggleChipGrid**
- `app/src/components/shared/ToggleChipGrid.tsx` — 신규
- `app/src/components/records/StrategyEmotionFields.tsx:29-65`
- `app/src/components/records/TradeEditPanel.tsx:299-363`
- `app/src/components/records/TradeMetaBuyForm.tsx:121-135`

## 구현 체크리스트

- [ ] `shared/ConfirmDeleteDialog.tsx` 신규
- [ ] `DeleteTradeDialog` 제거 + `TradeDetail.tsx` 호출부 치환
- [ ] `DeleteAccountDialog` 제거 + `AccountCard.tsx` 호출부 치환
- [ ] (커밋 1) `refactor(fe): ConfirmDeleteDialog 통합`
- [ ] `records/TradeHeaderCard.tsx` 신규
- [ ] `TradeDetail.tsx` 헤더 카드 치환
- [ ] `TradeEditPanel.tsx` 헤더 카드 치환
- [ ] (커밋 2) `refactor(fe): TradeHeaderCard 추출`
- [ ] `shared/ToggleChipGrid.tsx` 신규
- [ ] `StrategyEmotionFields.tsx` 2 곳 치환
- [ ] `TradeEditPanel.tsx` 3 곳 치환
- [ ] `TradeMetaBuyForm.tsx` 1 곳 치환
- [ ] (커밋 3) `refactor(fe): ToggleChipGrid 추출`
- [ ] `pnpm -C app exec tsc --noEmit` 그린
- [ ] `pnpm -C app test` 그린
- [ ] `docs/backlog.md` 처리 완료 3 항목 제거

## 우려사항 / 리스크

- **ConfirmDeleteDialog error padding 미세 차이** — DeleteTrade `px-1` vs DeleteAccount 없음. `px-1` 제거로 통일.
- **TradeHeaderCard 종목명 분기 3 가지** — props 미지정 시 plain span. TradeEditPanel 은 항상 plain.
- **ToggleChipGrid `emptyValue` 차이** — `""` vs `null` 호출부 타입 유지하기 위해 `emptyValue` prop 흡수.
- **항목별 1 커밋** — 각 커밋 후 타입체크 통과 확인.
- **DeleteTradeDialog/DeleteAccountDialog 파일 제거** — 호출부 각 1 곳뿐. 직접 사용으로 대체.
