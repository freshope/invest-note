"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { fmt } from "@/lib/format";
import { PNL_COLORS } from "@/lib/constants/colors";
import {
  CountryBadge,
  ExchangeBadge,
  MarketTypeBadge,
  getQuantityUnit,
} from "./trade-display";
import type { Trade } from "@/types/database";

interface TradeHeaderCardProps {
  trade: Pick<
    Trade,
    "asset_name" | "ticker_symbol" | "market_type" | "country_code" | "exchange"
  >;
  isBuy: boolean;
  totalAmount: number;
  price: number;
  quantity: number;
  onStockPress?: () => void;
  stockHref?: string | null;
}

export function TradeHeaderCard({
  trade,
  isBuy,
  totalAmount,
  price,
  quantity,
  onStockPress,
  stockHref,
}: TradeHeaderCardProps) {
  const accent = isBuy ? PNL_COLORS.rise : PNL_COLORS.fall;
  const hasStock = !!trade.ticker_symbol;
  const interactive = onStockPress && hasStock;

  return (
    <div className="rounded-2xl overflow-hidden bg-muted/60">
      <div className={cn("h-1", accent.bg)} />
      <div className="p-5">
        <div className="flex items-center gap-2 mb-1">
          {interactive ? (
            <button
              type="button"
              onClick={onStockPress}
              className="text-[20px] font-bold text-foreground underline-offset-2 hover:underline text-left"
            >
              {trade.asset_name}
            </button>
          ) : stockHref ? (
            <Link
              href={stockHref}
              className="text-[20px] font-bold text-foreground underline-offset-2 hover:underline"
            >
              {trade.asset_name}
            </Link>
          ) : (
            <span className="text-[20px] font-bold text-foreground">{trade.asset_name}</span>
          )}
          <span
            className={cn(
              "text-[12px] font-bold px-2 py-0.5 rounded-md",
              accent.bgSoft,
              accent.text,
            )}
          >
            {isBuy ? "매수" : "매도"}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {trade.ticker_symbol && (
            <span className="text-[13px] font-mono text-muted-foreground">
              {trade.ticker_symbol}
            </span>
          )}
          <MarketTypeBadge marketType={trade.market_type} />
          {trade.market_type === "STOCK" && (
            <>
              <CountryBadge countryCode={trade.country_code ?? "KR"} />
              <ExchangeBadge exchange={trade.exchange} />
            </>
          )}
        </div>
        <div className="mt-4 pt-4 border-t border-border/40">
          <p className={cn("text-[24px] font-bold tabular-nums text-right", accent.text)}>
            {fmt(totalAmount)}원
          </p>
          <p className="text-[12px] text-muted-foreground text-right mt-0.5 tabular-nums">
            {fmt(price)}원 × {quantity}
            {getQuantityUnit(trade.market_type)}
          </p>
        </div>
      </div>
    </div>
  );
}
