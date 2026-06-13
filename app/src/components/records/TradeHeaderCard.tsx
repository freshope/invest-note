"use client";

import Link from "next/link";
import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { currencyForCountry, formatMoney } from "@/lib/format";
import { MoneyText } from "@/components/shared/MoneyText";
import { getTradeTypeAccent } from "@/lib/constants/colors";
import { DEFAULT_COUNTRY_CODE } from "@/lib/constants/market";
import { TradeTypeBadge } from "@/components/shared/TradeTypeBadge";
import { StockMetaBadges } from "@/components/stocks/StockMetaBadges";
import { useStockMeta, isMetaCode } from "@/hooks/useStockMeta";
import {
  MarketTypeBadge,
  getQuantityUnit,
} from "./trade-display";
import type { Trade, TradeType } from "@/types/database";

interface TradeHeaderCardProps {
  trade: Pick<
    Trade,
    "asset_name" | "ticker_symbol" | "market_type" | "country_code" | "exchange" | "exchange_rate"
  >;
  tradeType: TradeType;
  totalAmount: number;
  price: number;
  quantity: number;
  onStockPress?: () => void;
  stockHref?: string | null;
}

export function TradeHeaderCard({
  trade,
  tradeType,
  totalAmount,
  price,
  quantity,
  onStockPress,
  stockHref,
}: TradeHeaderCardProps) {
  const accent = getTradeTypeAccent(tradeType);
  const hasStock = !!trade.ticker_symbol;
  const interactive = onStockPress && hasStock;

  const metaCodes = useMemo(
    () => (isMetaCode(trade.ticker_symbol, trade.country_code) ? [trade.ticker_symbol] : []),
    [trade.ticker_symbol, trade.country_code],
  );
  const { meta } = useStockMeta(metaCodes);
  const stockMeta = trade.ticker_symbol ? meta[trade.ticker_symbol] : undefined;

  return (
    <div className="rounded-2xl overflow-hidden bg-muted/60">
      <div className={cn("h-1", accent.bg)} />
      <div className="p-5">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          {interactive ? (
            <button
              type="button"
              onClick={onStockPress}
              className="min-w-0 break-words text-[20px] font-bold text-foreground underline-offset-2 hover:underline text-left"
            >
              {trade.asset_name}
            </button>
          ) : stockHref ? (
            <Link
              href={stockHref}
              className="min-w-0 break-words text-[20px] font-bold text-foreground underline-offset-2 hover:underline"
            >
              {trade.asset_name}
            </Link>
          ) : (
            <span className="min-w-0 break-words text-[20px] font-bold text-foreground">{trade.asset_name}</span>
          )}
          {trade.ticker_symbol && (
            <span className="text-[13px] font-mono text-muted-foreground">
              {trade.ticker_symbol}
            </span>
          )}
          <TradeTypeBadge tradeType={tradeType} size="md" />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <MarketTypeBadge marketType={trade.market_type} />
          {trade.market_type === "STOCK" && (
            <StockMetaBadges
              countryCode={trade.country_code ?? DEFAULT_COUNTRY_CODE}
              market={trade.exchange || stockMeta?.market}
              rank={stockMeta?.marcap_rank}
              nps={stockMeta?.nps_holding}
              npsAsOf={stockMeta?.nps_as_of}
              usIndex={stockMeta?.us_index}
            />
          )}
        </div>
        <div className="mt-4 pt-4 border-t border-border/40">
          <p className={cn("text-[24px] font-bold tabular-nums text-right", accent.text)}>
            <MoneyText
              krw={totalAmount * Number(trade.exchange_rate ?? 1)}
              native={totalAmount}
              currency={currencyForCountry(trade.country_code ?? DEFAULT_COUNTRY_CODE)}
              nativeClassName="text-[14px]"
            />
          </p>
          <p className="text-[12px] text-muted-foreground text-right mt-0.5 tabular-nums">
            {formatMoney(price, currencyForCountry(trade.country_code ?? DEFAULT_COUNTRY_CODE))} × {quantity}
            {getQuantityUnit(trade.market_type)}
          </p>
        </div>
      </div>
    </div>
  );
}
