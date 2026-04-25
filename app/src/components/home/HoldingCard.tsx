import { cn } from "@/lib/utils";
import { fmt } from "@/lib/format";
import type { Position } from "@/lib/portfolio";
import { CountryBadge } from "@/components/records/trade-display";

interface HoldingCardProps {
  position: Position;
  onPress?: () => void;
}

export function HoldingCard({ position, onPress }: HoldingCardProps) {
  const {
    assetName,
    ticker,
    country,
    holdingQuantity,
    avgBuyPrice,
    currentPrice,
    evaluation,
    unrealizedPnL,
    lastNote,
  } = position;

  const pnlPos = (unrealizedPnL ?? 0) > 0;
  const pnlNeg = (unrealizedPnL ?? 0) < 0;

  const priceChangePct =
    currentPrice !== null && avgBuyPrice > 0
      ? Math.round(((currentPrice - avgBuyPrice) / avgBuyPrice) * 10000) / 100
      : null;

  return (
    <button
      type="button"
      onClick={onPress}
      className="w-full text-left rounded-2xl bg-muted/60 p-4 space-y-3 active:scale-[0.98] transition-transform"
    >
      {/* 헤더 */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[16px] font-bold text-foreground">{assetName}</span>
            <CountryBadge countryCode={country} />
          </div>
          <p className="text-[12px] font-mono text-muted-foreground">{ticker}</p>
        </div>

        {/* 평가금액 */}
        <div className="text-right shrink-0">
          <p className="text-[16px] font-bold tabular-nums text-foreground">
            {evaluation !== null ? `${fmt(evaluation)}원` : "-"}
          </p>
          {unrealizedPnL !== null && (
            <p
              className={cn(
                "text-[12px] font-semibold tabular-nums",
                pnlPos && "text-[var(--rise)]",
                pnlNeg && "text-[var(--fall)]",
                !pnlPos && !pnlNeg && "text-muted-foreground",
              )}
            >
              {pnlPos ? "+" : ""}
              {fmt(unrealizedPnL)}원
            </p>
          )}
        </div>
      </div>

      {/* 수치 행 */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">현재가</p>
          <p
            className={cn(
              "text-[13px] font-semibold tabular-nums text-foreground",
              priceChangePct !== null && priceChangePct > 0 && "text-[var(--rise)]",
              priceChangePct !== null && priceChangePct < 0 && "text-[var(--fall)]",
            )}
          >
            {currentPrice !== null ? `${fmt(currentPrice)}` : "-"}
          </p>
          {priceChangePct !== null && (
            <p
              className={cn(
                "text-[11px] font-semibold tabular-nums",
                priceChangePct > 0 && "text-[var(--rise)]",
                priceChangePct < 0 && "text-[var(--fall)]",
                priceChangePct === 0 && "text-muted-foreground",
              )}
            >
              {priceChangePct > 0 ? "+" : ""}
              {priceChangePct.toFixed(2)}%
            </p>
          )}
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">매수단가</p>
          <p className="text-[13px] font-semibold tabular-nums text-foreground">
            {fmt(Math.round(avgBuyPrice))}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">보유수량</p>
          <p className="text-[13px] font-semibold tabular-nums text-foreground">
            {holdingQuantity.toLocaleString("ko-KR")}주
          </p>
        </div>
      </div>

      {/* 매수 근거 스니펫 */}
      {lastNote && (
        <div className="flex items-start gap-1.5 pt-1 border-t border-border/50">
          <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-md mt-0.5 bg-brand/10 text-[var(--brand)]">
            매수 근거
          </span>
          <p className="text-[12px] text-muted-foreground leading-relaxed line-clamp-2">
            {lastNote}
          </p>
        </div>
      )}
    </button>
  );
}
