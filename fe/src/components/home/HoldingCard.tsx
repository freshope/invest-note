import { memo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { calcChangePercent, fmt, formatPctSigned, formatPnL, signColor } from "@/lib/format";
import type { Position } from "@/lib/portfolio";
import { CountryBadge } from "@/components/records/trade-display";

interface HoldingCardProps {
  position: Position;
  // 부모가 카드마다 새 클로저를 만들지 않도록 position 자체를 인자로 전달한다.
  onPress?: (position: Position) => void;
}

export const HoldingCard = memo(function HoldingCard({ position, onPress }: HoldingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [pressing, setPressing] = useState(false);

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

  const hasMultipleLines = lastNote?.includes("\n") ?? false;
  const firstLine = lastNote?.split("\n")[0] ?? "";

  const priceChangePct =
    currentPrice !== null && avgBuyPrice > 0 ? calcChangePercent(currentPrice, avgBuyPrice) : null;

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${assetName} 보유 종목 상세`}
      onClick={() => onPress?.(position)}
      onPointerDown={() => setPressing(true)}
      onPointerUp={() => setPressing(false)}
      onPointerLeave={() => setPressing(false)}
      onPointerCancel={() => setPressing(false)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onPress?.(position);
        }
      }}
      data-pressing={pressing ? "true" : undefined}
      className="w-full text-left rounded-2xl bg-muted/60 p-4 space-y-3 transition-transform cursor-pointer data-[pressing=true]:scale-[0.98]"
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
                signColor(unrealizedPnL, "muted"),
              )}
            >
              {formatPnL(unrealizedPnL)}
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
              priceChangePct !== null && signColor(priceChangePct, "none"),
            )}
          >
            {currentPrice !== null ? `${fmt(currentPrice)}` : "-"}
          </p>
          {priceChangePct !== null && (
            <p
              className={cn(
                "text-[11px] font-semibold tabular-nums",
                signColor(priceChangePct, "muted"),
              )}
            >
              {formatPctSigned(priceChangePct)}
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
            {fmt(holdingQuantity)}주
          </p>
        </div>
      </div>

      {/* 매수 근거 스니펫 */}
      {lastNote && (
        <div
          className={cn(
            "flex gap-1.5 pt-2 border-t border-border/50",
            expanded ? "items-start" : "items-center",
            hasMultipleLines && "cursor-pointer",
          )}
          onPointerDown={(e) => { if (hasMultipleLines) e.stopPropagation(); }}
          onClick={(e) => {
            if (!hasMultipleLines) return;
            e.stopPropagation();
            setExpanded((prev) => !prev);
          }}
        >
          <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-brand/10 text-[var(--brand)]">
            매수 근거
          </span>
          <p
            className={cn(
              "flex-1 text-[12px] text-muted-foreground leading-relaxed",
              expanded ? "whitespace-pre-line" : "line-clamp-1",
            )}
          >
            {expanded ? lastNote : firstLine}
          </p>
          {hasMultipleLines && (
            <span
              aria-hidden
              className="shrink-0 text-muted-foreground/60 p-0.5"
            >
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </span>
          )}
        </div>
      )}
    </div>
  );
});
