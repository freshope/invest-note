# Spec: Frontend simplify 후속 — sign-color helper 도입

## 배경 / 문제

직전 `/simplify fe 전체 범위 조사`로 18 파일을 정리했고(현재 브랜치로 이전된 미커밋 상태), 이어진 `/review`에서 4가지 후속 정리 항목이 식별되었습니다.

- **A.** `records/constants.ts` shim 장기 정리 — 5 consumer 일괄 교체 필요
- **B.** `HoldingCard.priceChangePct` % 부호 포매팅 — 단일 사이트
- **C.** `AdherencePnL` (StrategyAdherencePanel 로컬) vs `analysis/PnLLine` 분리 사유 주석 필요
- **D.** sign-color ternary `value > 0 ? "text-[var(--rise)]" : value < 0 ? "text-[var(--fall)]" : ...` 중복 — 7+ 사이트

**범위 결정:** D는 가치가 크므로 helper로 통합. C는 1줄 주석. A·B는 backlog로 이월(A=churn, B=단일 사이트).

## 목표

- `lib/format.ts`에 `signColor(value, fallback)` 헬퍼가 존재하고, sign-based 7곳이 이를 사용한다.
- `StrategyAdherencePanel`의 `AdherencePnL` 위에 분리 사유 1줄 주석이 있다.
- `docs/backlog.md`에 항목 A·B가 후속 작업으로 등록된다.
- `pnpm tsc --noEmit` 통과, `pnpm test` 통과.

## 설계

### 접근 방식

`lib/format.ts`에 다음 헬퍼 추가:

```ts
type SignFallback = "foreground" | "muted" | "none";

export function signColor(value: number, fallback: SignFallback = "foreground"): string {
  if (value > 0) return "text-[var(--rise)]";
  if (value < 0) return "text-[var(--fall)]";
  if (fallback === "muted") return "text-muted-foreground";
  if (fallback === "none") return "";
  return "text-foreground";
}
```

- `"foreground"` (기본): 0일 때 일반 텍스트 — 카드 통계 영역
- `"muted"`: 0일 때 흐림 — chip/sub-text
- `"none"`: 0일 때 부모 색상 상속 — 색상 변경 없는 컨텍스트

### 적용 사이트 (sign-based 7곳)

| # | 파일:라인 | 변수 | fallback |
|---|----------|------|----------|
| 1 | `components/home/DashboardSummary.tsx:13-19` (`PnLText`) | `value` | `"foreground"` |
| 2 | `components/home/HoldingCard.tsx:77-83` | `unrealizedPnL` | `"muted"` |
| 3 | `components/home/HoldingCard.tsx:104-110` | `priceChangePct` | `"muted"` |
| 4 | `components/stocks/StockDetail.tsx:94-100` | `stats.totalProfitLoss` | `"foreground"` |
| 5 | `components/analysis/SummaryCards.tsx:44-49` (`pnlClass`) | `totalProfitLoss` | `"foreground"` |
| 6 | `components/analysis/PnLLine.tsx:14-18` | `value` (0 early-return) | `"none"` |
| 7 | `components/analysis/StrategyAdherencePanel.tsx:13-25` (`AdherencePnL`) | `value` (0 early-return) | `"none"` |

### 범위 밖 (의도적 제외)

- `TradeCard.tsx:57-59` — `TradeResult` enum
- `TradeDetail.tsx:156, TradeEditPanel.tsx:197` — boolean (isBuy/isSell)
- `WinRateBar`, `ReviewQualityPanel`, `DiversificationPanel`, `SummaryCards.winRateClass` — threshold 기반
- `TradeDetail.tsx:201-202, 234-235` — sign-based이지만 적용 시 행동 변경 가능 → 검토 후 결정

### 주요 변경 파일

- `app/src/lib/format.ts` — `signColor` 헬퍼 추가
- `app/src/components/home/DashboardSummary.tsx` — `PnLText`에 적용
- `app/src/components/home/HoldingCard.tsx` — 2곳 (unrealizedPnL, priceChangePct)
- `app/src/components/stocks/StockDetail.tsx` — totalProfitLoss
- `app/src/components/analysis/SummaryCards.tsx` — pnlClass
- `app/src/components/analysis/PnLLine.tsx` — value
- `app/src/components/analysis/StrategyAdherencePanel.tsx` — `AdherencePnL` + 분리 사유 주석
- `docs/backlog.md` — 항목 A·B 등록

## 구현 체크리스트

- [x] `app/src/lib/format.ts`에 `SignFallback` 타입과 `signColor` 함수 추가
- [x] `DashboardSummary.tsx` `PnLText` cn 인자 → `signColor(value, "foreground")`
- [x] `HoldingCard.tsx` (unrealizedPnL) → `signColor(unrealizedPnL, "muted")`
- [x] `HoldingCard.tsx` (priceChangePct) → 2곳: 현재가 라인 `"none"`, 변동률 라인 `"muted"`
- [x] `StockDetail.tsx` totalProfitLoss → `signColor(stats.totalProfitLoss, "foreground")`
- [x] `SummaryCards.tsx` `pnlClass` → `signColor(totalProfitLoss, "foreground")`
- [x] `PnLLine.tsx` → `signColor(value, "none")`
- [x] `StrategyAdherencePanel.tsx`: 분리 사유 주석 + `signColor(value, "none")`
- [x] `docs/backlog.md`에 항목 A·B 추가
- [x] `pnpm -C app exec tsc --noEmit` 통과
- [x] `pnpm -C app test` 통과

## 우려사항 / 리스크

- **0일 때 색상 변경**: `summary.pnl === 0` 같은 미적용 케이스가 신규 fallback 옵션에 따라 동일 동작인지 시각 확인 필요.
- **`HoldingCard:97-99`** (현재가): `priceChangePct === 0`일 때 fallback이 다른 라인과 차이 — 적용 여부 검토.
- **`PnLText`의 `cn` 사용**: `signColor`는 단일 문자열 반환 → `cn(..., signColor(value, "foreground"), className)` 형태로 합성.
