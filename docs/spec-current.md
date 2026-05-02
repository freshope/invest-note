# Spec: FE simplify Round 7 — `EmptyCard` 추출

## 배경 / 문제

`/simplify` Round 1~6 후속으로 백로그(`docs/backlog.md`)에 남은 "컴포넌트 추출 (중복 제거)" 항목 중 하나를 처리한다.

> `EmptyCard` 일반화 — `home/EmptyState` 를 일반화하거나 `shared/EmptyCard` 신규. `TradeList` / `AccountList` / `StockDetail` 의 "데이터 없음" 카드 패턴 통합

현재 동일/유사한 "빈 상태 카드" 마크업이 5곳에서 반복된다.

| 위치 | 스타일 | 메시지 / action |
|------|--------|----------------|
| `components/home/EmptyState.tsx` | `rounded-2xl bg-muted/60 p-8 text-center space-y-4` | variant("no-accounts"/"no-trades") + `<Link>` 버튼 |
| `records/TradeList.tsx:52-58` | 위 + `mt-2` | "거래 기록이 없어요" — action 없음 |
| `records/TradeList.tsx:59-65` | 위 + `mt-2` | "해당 계좌의 기록이 없어요" — action 없음 |
| `settings/AccountList.tsx:20-32` | 위와 동일 | "등록된 계좌가 없어요" + `<Button>` action |
| `stocks/StockDetail.tsx:110-117` | `... space-y-1` (좁은 간격, title 14px) | 필터 상태에 따라 메시지 분기 |

스타일이 일관되어 있고, 메시지·action 만 다르므로 단일 `EmptyCard` 로 흡수할 수 있다. `BreakdownList` / `TradeHeaderCard` / `ProgressTrack` 추출과 동일 결의 정리 작업.

> 통합 제외 항목 (의도적):
> - `ImportTradesPanel/AccountStep.tsx` — `rounded-lg border border-dashed` + `AlertCircleIcon`. 톤이 다른 경고형 빈 상태.
> - `home/AllocationTabs.tsx` — `flex h-40 items-center justify-center`. 차트 내부 placeholder, 카드 셸이 아님.

## 목표

- `components/shared/EmptyCard.tsx` 신규 컴포넌트가 표준 빈 상태 카드 셸을 책임진다
- 기존 `home/EmptyState` 가 `EmptyCard` 위에서 재구성되어 동일 외관을 유지한다
- `TradeList` / `AccountList` / `StockDetail` 의 인라인 빈 상태 마크업이 `EmptyCard` 호출로 치환된다
- `pnpm tsc` 통과
- `pnpm -C app test` 통과

## 설계

### `EmptyCard` API

```tsx
interface EmptyCardProps {
  title: string;
  description?: ReactNode;        // <br/> 포함 가능
  action?: ReactNode;             // <Button> / <Link> 자유 슬롯
  className?: string;             // 외부 여백(mt-2 등) 흡수
  compact?: boolean;              // StockDetail 변종: space-y-1 + title 14px
}
```

내부 구조:

```tsx
<div className={cn(
  "rounded-2xl bg-muted/60 p-8 text-center",
  compact ? "space-y-1" : "space-y-4",
  className,
)}>
  <p className={cn(
    "font-semibold text-foreground",
    compact ? "text-[14px]" : "text-[15px]",
  )}>{title}</p>
  {description && (
    <p className="text-[13px] text-muted-foreground leading-relaxed">
      {description}
    </p>
  )}
  {action}
</div>
```

### `home/EmptyState` 재구성

기존 variant API 유지, 내부만 `EmptyCard` 로 위임.

### 호출부 치환 (4건)

1. `records/TradeList.tsx:52-58` → `<EmptyCard className="mt-2" title=… description=… />`
2. `records/TradeList.tsx:59-65` → 동일 패턴
3. `settings/AccountList.tsx:20-32` → action 슬롯에 `<Button>` 이동
4. `stocks/StockDetail.tsx:110-117` → `compact` prop 사용

### 주요 변경 파일

- `app/src/components/shared/EmptyCard.tsx` — 신규
- `app/src/components/home/EmptyState.tsx` — `EmptyCard` 위로 재구성 (외부 API 유지)
- `app/src/components/records/TradeList.tsx` — 인라인 빈 상태 2건 치환
- `app/src/components/settings/AccountList.tsx` — 인라인 빈 상태 1건 치환
- `app/src/components/stocks/StockDetail.tsx` — 인라인 빈 상태 1건 치환 (compact)
- `docs/backlog.md` — Round 7 처리 메모

## 구현 체크리스트

- [ ] `components/shared/EmptyCard.tsx` 신규 생성
- [ ] `home/EmptyState.tsx` 를 `EmptyCard` 위로 재구성
- [ ] `records/TradeList.tsx` 인라인 빈 상태 2건 → `EmptyCard` 치환
- [ ] `settings/AccountList.tsx` 인라인 빈 상태 → `EmptyCard` 치환
- [ ] `stocks/StockDetail.tsx` 인라인 빈 상태 → `EmptyCard compact` 치환
- [ ] `docs/backlog.md` Round 7 처리 메모
- [ ] 타입 체크 (`pnpm tsc`)
- [ ] FE 단위 테스트 (`pnpm -C app test`)

## 우려사항 / 리스크

- `space-y-1` vs `space-y-4` 변종 — `compact` prop 흡수
- `description` 이 `<br />` 포함 → `ReactNode` 로 받음
- `EmptyCard` 는 `components/shared/` 에 두 — `BreakdownList` 와 결정 패턴 비교 (분석 도메인 한정 컴포넌트만 `analysis/` 에 둔다)
- `AccountStep`/`AllocationTabs` 는 톤 차이로 의도적으로 제외
