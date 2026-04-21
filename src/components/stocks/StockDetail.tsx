"use client";

import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { groupByDate, formatDateLabel, type TradeWithAccount } from "@/lib/trade-utils";
import { TradeCard } from "@/components/records/TradeCard";
import { ChevronLeftIcon } from "lucide-react";
import { CountryBadge } from "@/components/records/trade-display";

interface StockStats {
  totalTrades: number;
  sellCount: number;
  winCount: number;
  totalProfitLoss: number;
}

interface StockDetailProps {
  assetName: string;
  ticker: string;
  country: string;
  trades: TradeWithAccount[];
  stats: StockStats;
  onBack?: () => void;
  onTradePress?: (trade: TradeWithAccount) => void;
}

export function StockDetail({ assetName, ticker, country, trades, stats, onBack, onTradePress }: StockDetailProps) {
  const router = useRouter();
  const grouped = groupByDate(trades);

  const winRate = stats.sellCount > 0
    ? Math.round((stats.winCount / stats.sellCount) * 100)
    : null;

  const pnlPositive = stats.totalProfitLoss > 0;
  const pnlNegative = stats.totalProfitLoss < 0;

  return (
    <>
      {/* 헤더 */}
      <div
        className="sticky top-0 z-10 bg-background"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="relative flex h-14 items-center px-2">
          <button
            type="button"
            onClick={onBack ?? (() => router.back())}
            className="flex h-10 w-10 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted active:bg-muted"
            aria-label="뒤로"
          >
            <ChevronLeftIcon className="h-6 w-6" strokeWidth={2.2} />
          </button>
          <span className="absolute inset-x-0 text-center text-[17px] font-bold text-foreground pointer-events-none truncate px-14">
            {assetName}
          </span>
        </div>
      </div>

      <div className="px-5 pb-8 space-y-5">
        {/* 종목 기본 정보 */}
        <div className="rounded-2xl bg-muted/60 p-4">
          <div className="flex items-center gap-2">
            <span className="text-[22px] font-bold text-foreground">{assetName}</span>
            <CountryBadge countryCode={country} />
          </div>
          <span className="text-[13px] font-mono text-muted-foreground">{ticker}</span>
        </div>

        {/* 성과 요약 */}
        <div>
          <p className="text-[13px] font-semibold text-muted-foreground mb-2">성과 요약</p>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-2xl bg-muted/60 p-4 text-center">
              <p className="text-[22px] font-bold text-foreground">{stats.totalTrades}</p>
              <p className="text-[12px] text-muted-foreground mt-0.5">총 거래</p>
            </div>
            <div className="rounded-2xl bg-muted/60 p-4 text-center">
              <p className="text-[22px] font-bold text-foreground">
                {winRate !== null ? `${winRate}%` : "-"}
              </p>
              <p className="text-[12px] text-muted-foreground mt-0.5">승률</p>
            </div>
            <div className="rounded-2xl bg-muted/60 p-4 text-center">
              <p className={cn(
                "text-[18px] font-bold",
                pnlPositive && "text-[var(--rise)]",
                pnlNegative && "text-[var(--fall)]",
                !pnlPositive && !pnlNegative && "text-foreground",
              )}>
                {stats.totalProfitLoss !== 0
                  ? `${pnlPositive ? "+" : ""}${Math.round(stats.totalProfitLoss / 10000)}만`
                  : "-"}
              </p>
              <p className="text-[12px] text-muted-foreground mt-0.5">총 손익</p>
            </div>
          </div>
        </div>

        {/* 거래 히스토리 */}
        <div>
          <p className="text-[13px] font-semibold text-muted-foreground mb-2">거래 히스토리</p>
          {trades.length === 0 ? (
            <div className="rounded-2xl bg-muted/60 p-8 text-center">
              <p className="text-[14px] text-muted-foreground">거래 기록이 없습니다</p>
            </div>
          ) : (
            <div className="space-y-6">
              {grouped.map(([dateKey, dayTrades]) => (
                <div key={dateKey}>
                  <p className="text-[13px] font-semibold text-muted-foreground mb-2">
                    {formatDateLabel(dateKey)}
                  </p>
                  <div className="space-y-2">
                    {dayTrades.map((trade) => (
                      <TradeCard
                        key={trade.id}
                        trade={trade}
                        onPress={onTradePress ? () => onTradePress(trade) : undefined}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
