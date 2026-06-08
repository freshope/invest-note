# Spec: FE simplify Round 3 — AccountChip 추출

> 완료: 2026-04-30

## 배경 / 문제

Round 2 (`docs/issue-history/2026-04-30-fe-simplify-round2-component-extract.md`) 에서 `ConfirmDeleteDialog` / `TradeHeaderCard` / `ToggleChipGrid` 3 개를 처리한 뒤, `docs/backlog.md` 의 "FE simplify (Round 1 이후 deferred) — 컴포넌트 추출 (중복 제거)" 섹션에 6 개 후보가 남았다.

탐색 결과 `AccountChip` (7 곳) 이 중복 빈도가 가장 높고 디자인 결정 범위가 좁아 단일 라운드로 안전하게 처리 가능하다고 판단했다. 나머지 5 개 (TradeTypeBadge / BreakdownList / ProgressTrack / EmptyCard / Card primitive) 는 backlog 에 보존한다.

**기대 효과:** `BrokerLogo + 계좌명` inline-flex 마크업 7 곳 일원화. 이후 계좌 표시 포맷 변경 (예: 약어/풀네임 토글) 시 단일 지점만 수정.

## 목표

1. `AccountChip` 컴포넌트를 신규 추가하고, 아래 7 호출부의 `BrokerLogo + 계좌명` inline-flex 마크업을 모두 `AccountChip` 으로 치환한다.
2. size prop 으로 기존 BrokerLogo 사이즈 스펙트럼 (14 / 16 / 18 / 20 → sm / md / lg) 흡수. 기존 시각적 사이즈 유지.
3. 호출부 truncate / overflow / text-size 차이는 `className` prop 으로 흡수.
4. `pnpm -C app exec tsc --noEmit` 그린, `pnpm -C app test` 그린, 회귀 없음.

## 설계

### 접근 방식

Round 2 패턴 답습 — 신규 컴포넌트는 `app/src/components/shared/` 배치, 호출부 1 곳씩 치환하되 한 커밋으로 묶는다 (Round 2 의 `ToggleChipGrid` 처럼 동일 패턴 다수 치환은 1 커밋이 자연스러움).

### 컴포넌트 시그니처

```tsx
type AccountChipProps = {
  account: Pick<Account, "broker" | "name">;
  size?: "sm" | "md" | "lg"; // 14 / 16 / 20 — default "md"
  className?: string;          // 컨테이너 클래스 (text size·truncate 등)
};
```

내부 마크업 (sketch):

```tsx
<span className={cn("inline-flex min-w-0 items-center", GAP[size], className)}>
  <BrokerLogo broker={account.broker} size={SIZE_PX[size]} />
  <span className="truncate">{account.name}</span>
</span>
```

- `GAP`: `{ sm: "gap-1", md: "gap-1.5", lg: "gap-1.5" }`
- `SIZE_PX`: `{ sm: 14, md: 16, lg: 20 }`
- `min-w-0` + 내부 `truncate` 로 부모 flex 컨테이너 안에서 잘림 처리 일관화

### 호출부 매핑 (탐색 결과 기준)

| 위치 | 기존 BrokerLogo size | 매핑 size | 비고 |
|------|---------------------|-----------|------|
| `TradeCard.tsx:81-83` | 14 | `sm` | text-[12px] 는 className 으로 |
| `TradeDetail.tsx:150` | 16 | `md` | gap-1 → gap-1.5 (미세 차이 허용) |
| `TradeEditPanel.tsx:179-181` | 16 | `md` | 동일 |
| `TradeBasicForm.tsx:296` (Select trigger) | 16 | `md` | overflow-hidden 은 className |
| `TradeBasicForm.tsx:310` (Select item) | 16 | `md` | 동일 |
| `AccountFilter.tsx:37-41` | 18 | `md` | 18 → 16 통일 (시각 차이 미미) |
| `AccountCard.tsx:50-54` | 20 | `lg` | 큰 카드 메인 |

`AccountFilter` 의 18 → 16 통일은 의도적 사이즈 정규화. 시각 회귀 우려 시 `lg` (20) 로 변경 가능하나 16 이 다수 호출부와 일치하므로 `md` 채택.

### 주요 변경 파일

- `app/src/components/shared/AccountChip.tsx` — **신규**
- `app/src/components/records/TradeCard.tsx` — 치환
- `app/src/components/records/TradeDetail.tsx` — 치환
- `app/src/components/records/TradeEditPanel.tsx` — 치환
- `app/src/components/records/TradeBasicForm.tsx` — 2 곳 치환
- `app/src/components/records/AccountFilter.tsx` — 치환
- `app/src/components/settings/AccountCard.tsx` — 치환

## 구현 체크리스트

- [x] `app/src/components/shared/AccountChip.tsx` 신규 작성
- [x] `TradeCard.tsx` 호출부 치환 (size=sm)
- [x] `TradeDetail.tsx` 호출부 치환 (size=md)
- [x] `TradeEditPanel.tsx` 호출부 치환 (size=md)
- [x] `TradeBasicForm.tsx` 2 곳 치환 (Select trigger/item, size=md)
- [x] `AccountFilter.tsx` 호출부 치환 (size=md, 18 → 16 통일)
- [x] `AccountCard.tsx` 호출부 치환 (size=lg)
- [x] (커밋 1) `refactor(fe): AccountChip 추출 — BrokerLogo+계좌명 7 곳 일원화`
- [x] `pnpm -C app exec tsc --noEmit` 그린
- [x] `pnpm -C app test` 그린
- [x] `docs/backlog.md` 의 AccountChip 항목 제거

## 우려사항 / 리스크

- **AccountFilter size 18 → 16 정규화** — 시각 회귀 우려. 모바일 360px 에서 칩 라인업 확인. 회귀 발견 시 size prop 에 추가 단계 (`md-plus` = 18) 또는 호출부에서 `lg` 사용.
- **TradeCard text-[12px] 처리** — 기본 폰트 사이즈로 회귀하지 않도록 `className="text-[12px]"` 명시.
- **min-w-0 부모 의존성** — `inline-flex` 자체의 truncate 는 부모 flex 컨테이너의 `min-w-0` 가 필요. TradeBasicForm Select 의 기존 `overflow-hidden` 은 className 으로 보존.
- **Account 타입 의존** — `Pick<Account, "broker" | "name">` 로 좁혀 import 부담 최소화.
- **TRADE_TYPE_LABELS / 기타 5 후보** — 본 라운드 범위 외. backlog 유지.
