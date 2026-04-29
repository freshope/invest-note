# Spec: TradeDetail signColor 적용

> 완료: 2026-04-29

## 배경 / 문제

`TradeDetail.tsx`에 sign-based 인라인 ternary 패턴이 두 곳 남아 있다 (line 199-206, 232-239 의 `summary.pnl > 0/<0 && "text-[var(--rise|fall)]"`).

다른 sign-based 7곳은 `simplify-fe-followup`에서 `signColor(value, fallback)` 헬퍼(`app/src/lib/format.ts:45-51`)로 통합 완료. TradeDetail 두 곳은 0일 때 색 변경 없음 동작이 같음을 시각 검증한 후 적용하기로 보류한 상태(`docs/backlog.md:22`).

본 작업은 두 곳을 시각 동작 변경 없이 `signColor`로 통합하여 sign-based 색 분기 단일 SOT를 완성한다.

## 목표

- `TradeDetail.tsx`의 sign-based 인라인 ternary 두 곳을 `signColor(summary.pnl, "none")`로 통합
- 시각적 동작 변경 없음 — 0/양수/음수 모든 경우 동일 클래스 적용
- 백로그 항목 제거

## 설계

### 핵심 결정: `"none"` 모드 사용

두 위치 모두 base className(`"text-[16|13]px font-bold tabular-nums"`)에 색상 클래스를 명시하지 않는다. 따라서 0일 때 부모 wrapper의 색을 상속받음(자연스럽게 foreground).

- `signColor(value, "none")` → 0일 때 `""` (빈 문자열) → 부모 상속 → **현재와 동일**
- `signColor(value, "foreground")` → 0일 때 `"text-foreground"` 명시 → 부모 색이 변경되면 동작 분기 (현재와 미세하게 다름)

따라서 정확한 동작 동등성을 위해 `"none"` 모드 사용. 다른 sign-based 사이트(`HoldingCard.tsx:92`, `PnLLine.tsx:14`, `StrategyAdherencePanel.tsx:17`)에서도 0 early-return 또는 부모 상속 의도일 때 `"none"`을 사용 — 동일 컨벤션.

### 변경 위치 및 코드

**위치 1 — line 199-206 (거래 결과 카드 헤더의 손익액):**

```tsx
// before
<span className={cn(
  "text-[16px] font-bold tabular-nums",
  summary.pnl > 0 && "text-[var(--rise)]",
  summary.pnl < 0 && "text-[var(--fall)]",
)}>
  {formatPnL(summary.pnl)}
</span>

// after
<span className={cn(
  "text-[16px] font-bold tabular-nums",
  signColor(summary.pnl, "none"),
)}>
  {formatPnL(summary.pnl)}
</span>
```

**위치 2 — line 232-239 (breakdown 박스의 실현손익):**

`summary.pnl != null` 가드는 이미 외부 `formatPnL(summary.pnl) : "–"` 텍스트 분기와 함께 살아 있고, `signColor` 인자가 number를 요구하므로 가드는 유지한 채 conditional로 묶는다.

```tsx
// before
<span className={cn(
  "text-[13px] font-bold tabular-nums",
  summary.pnl != null && summary.pnl > 0 && "text-[var(--rise)]",
  summary.pnl != null && summary.pnl < 0 && "text-[var(--fall)]",
)}>
  {summary.pnl != null ? formatPnL(summary.pnl) : "–"}
</span>

// after
<span className={cn(
  "text-[13px] font-bold tabular-nums",
  summary.pnl != null && signColor(summary.pnl, "none"),
)}>
  {summary.pnl != null ? formatPnL(summary.pnl) : "–"}
</span>
```

### 주요 변경 파일

- `app/src/components/records/TradeDetail.tsx` — `signColor` import 추가, line 199-206 / 232-239 두 곳 치환
- `docs/backlog.md` — line 22 항목 제거

## 구현 체크리스트

- [x] `app/src/components/records/TradeDetail.tsx`: `@/lib/format`에서 `signColor` import 추가
- [x] line 199-206 인라인 ternary → `signColor(summary.pnl, "none")` 치환
- [x] line 232-239 인라인 ternary → `summary.pnl != null && signColor(summary.pnl, "none")` 치환
- [x] `docs/backlog.md` 의 `TradeDetail` sign-based 항목 제거
- [x] 타입 체크 통과 (`pnpm tsc`)
- [x] (선택) 거래 상세 패널에서 SUCCESS / FAIL / BREAKEVEN 케이스 시각 확인

## 검증

1. 타입 체크: `pnpm tsc` 통과
2. 시각 회귀: 거래 상세 패널에서 매도(SELL) 거래 3종(이익/손실/본전) 열어서 색상 확인
   - 양수: `text-[var(--rise)]`(녹색) 적용
   - 음수: `text-[var(--fall)]`(빨강) 적용
   - 0(본전): 부모 wrapper 색 상속 (현재와 동일)

## 우려사항 / 리스크

- **시각 변경 가능성:** 매우 낮음. base className에 색이 없어 `"none"` 모드 빈 문자열과 인라인 ternary 미매칭(undefined → cn() 무시)이 결과적으로 같은 클래스 집합 생성.
- **`summary.pnl != null` 가드 보존:** 위치 2는 현재 ternary 두 줄에 모두 `!= null` 체크 중. 단일 conditional로 합쳐도 `signColor` 인자 안전성 동일하게 보장됨.
