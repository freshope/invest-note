import { memo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  calcChangePercent,
  fmt,
  formatMoney,
  formatPctSigned,
  formatPnLCurrency,
  signColor,
} from "@/lib/format";
import type { Position } from "@/lib/portfolio";
import type { StockMeta } from "@/lib/api-client";
import { StockMetaBadges } from "@/components/stocks/StockMetaBadges";
import { MoneyText } from "@/components/shared/MoneyText";

interface HoldingCardProps {
  position: Position;
  meta?: StockMeta;
  // 부모가 카드마다 새 클로저를 만들지 않도록 position 자체를 인자로 전달한다.
  onPress?: (position: Position) => void;
}

export const HoldingCard = memo(function HoldingCard({ position, meta, onPress }: HoldingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [pressing, setPressing] = useState(false);

  const {
    assetName,
    ticker,
    country,
    exchange,
    currency,
    holdingQuantity,
    avgBuyPrice,
    avgBuyPriceNative,
    currentPrice,
    evaluation,
    evaluationNative,
    unrealizedPnL,
    lastNote,
  } = position;

  const hasMultipleLines = lastNote?.includes("\n") ?? false;
  const firstLine = lastNote?.split("\n")[0] ?? "";

  const isForeign = currency !== "KRW";

  // 등락률은 native 시세(currentPrice) vs native 평단(avgBuyPriceNative) — 환율 영향 배제.
  const priceChangePct =
    currentPrice !== null && avgBuyPriceNative > 0
      ? calcChangePercent(currentPrice, avgBuyPriceNative)
      : null;

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
          <p className="min-w-0 break-words text-[16px] font-bold text-foreground">
            {assetName}{" "}
            <span className="text-[12px] font-mono font-normal text-muted-foreground">{ticker}</span>
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <StockMetaBadges
              countryCode={country}
              market={exchange || meta?.market}
              rank={meta?.marcap_rank}
              nps={meta?.nps_holding}
              npsAsOf={meta?.nps_as_of}
              usIndex={meta?.us_index}
            />
          </div>
        </div>

        {/* 평가금액 — 원화 primary, 해외는 달러 보조 병기 */}
        <div className="text-right shrink-0">
          <p className="text-[16px] font-bold tabular-nums text-foreground">
            {evaluation !== null ? (
              <MoneyText
                krw={evaluation}
                native={evaluationNative}
                currency={currency}
                nativeClassName="text-[12px]"
              />
            ) : (
              "-"
            )}
          </p>
          {unrealizedPnL !== null && (
            <p
              className={cn(
                "text-[12px] font-semibold tabular-nums",
                signColor(unrealizedPnL, "muted"),
              )}
            >
              {formatPnLCurrency(unrealizedPnL, "KRW")}
            </p>
          )}
        </div>
      </div>

      {/* 수치 행 — 현재가/매수단가는 native 통화(비교 가능). 평가/손익은 위 KRW. */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">현재가</p>
          <p
            className={cn(
              "text-[13px] font-semibold tabular-nums text-foreground",
              priceChangePct !== null && signColor(priceChangePct, "none"),
            )}
          >
            {currentPrice !== null
              ? isForeign
                ? formatMoney(currentPrice, currency)
                : fmt(currentPrice)
              : "-"}
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
            {isForeign ? formatMoney(avgBuyPriceNative, currency) : fmt(Math.round(avgBuyPrice))}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">보유수량</p>
          <p className="text-[13px] font-semibold tabular-nums text-foreground">
            {fmt(holdingQuantity)}주
          </p>
        </div>
      </div>

      {/* 매수 메모 스니펫 */}
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
            매수 메모
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
