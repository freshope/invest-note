"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { signColor } from "@/lib/format";
import { groupByDate, formatDateLabel, type TradeWithAccount } from "@/lib/trade-utils";
import { TradeCard } from "@/components/records/TradeCard";
import { ChevronLeftIcon, ChevronDownIcon, ChartSplineIcon } from "lucide-react";
import { StockMetaBadges } from "@/components/stocks/StockMetaBadges";
import { useStockMeta, isMetaCode } from "@/hooks/useStockMeta";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { PNL_COLORS } from "@/lib/constants/colors";
import { AccountFilter } from "@/components/shared/AccountFilter";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { useAccountFilter, useEffectiveAccountId } from "@/components/providers/AccountFilterProvider";
import type { Account } from "@/types/database";

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
  accounts: Account[];
  holdingQuantity?: number;
  onBack?: () => void;
  onTradePress?: (trade: TradeWithAccount) => void;
  onAssetHistoryPress?: () => void;
  onSwitchStock?: () => void;
  onBuy?: () => void;
  onSell?: () => void;
}

export function StockDetail({ assetName, ticker, country, trades, stats, accounts, holdingQuantity = 0, onBack, onTradePress, onAssetHistoryPress, onSwitchStock, onBuy, onSell }: StockDetailProps) {
  const router = useRouter();
  const { setSelectedAccountId } = useAccountFilter();
  const effectiveAccountId = useEffectiveAccountId(accounts);
  const isFiltered = effectiveAccountId !== null;
  const grouped = useMemo(() => groupByDate(trades), [trades]);

  const metaCodes = useMemo(
    () => (isMetaCode(ticker, country) ? [ticker] : []),
    [ticker, country],
  );
  const { meta } = useStockMeta(metaCodes);
  const stockMeta = meta[ticker];

  const winRate = stats.sellCount > 0
    ? Math.round((stats.winCount / stats.sellCount) * 100)
    : null;

  return (
    <>
      {/* 헤더 */}
      <div
        className="sticky top-0 z-10 bg-background"
        style={{ paddingTop: "var(--safe-area-inset-top, env(safe-area-inset-top))" }}
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
          {/* 컨테이너는 pointer-events-none 유지 → 클릭이 좌/우 버튼으로 통과. 중앙 버튼만 pointer-events-auto */}
          <div className="absolute inset-x-0 flex justify-center px-24 pointer-events-none">
            {onSwitchStock ? (
              <button
                type="button"
                onClick={onSwitchStock}
                className="pointer-events-auto inline-flex max-w-full items-center gap-1 text-[17px] font-bold text-foreground"
                aria-label="종목 변경"
              >
                <span className="min-w-0 truncate">{assetName}</span>
                <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" strokeWidth={2.4} />
              </button>
            ) : (
              <span className="min-w-0 truncate text-[17px] font-bold text-foreground">{assetName}</span>
            )}
          </div>
          {onAssetHistoryPress && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onAssetHistoryPress}
              className="ml-auto"
            >
              <ChartSplineIcon />
              자산 추이
            </Button>
          )}
        </div>
        {accounts.length >= 2 && (
          <AccountFilter accounts={accounts} value={effectiveAccountId} onChange={setSelectedAccountId} />
        )}
      </div>

      {/* flex-1: 콘텐츠가 짧아도 아래 액션바를 화면 바닥으로 밀어낸다(부모가 flex flex-col 전체 높이). */}
      <div className="flex-1 px-5 pb-8 space-y-5">
        {/* 종목 기본 정보 */}
        <div className="rounded-2xl bg-muted/60 p-4">
          <p className="min-w-0 break-words text-[22px] font-bold text-foreground">
            {assetName}{" "}
            <span className="text-[13px] font-mono font-normal text-muted-foreground">{ticker}</span>
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <StockMetaBadges
              countryCode={country}
              market={trades.find((t) => t.exchange)?.exchange || stockMeta?.market}
              rank={stockMeta?.marcap_rank}
              nps={stockMeta?.nps_holding}
              npsAsOf={stockMeta?.nps_as_of}
              usIndex={stockMeta?.us_index}
            />
          </div>
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
                signColor(stats.totalProfitLoss, "foreground"),
              )}>
                {stats.totalProfitLoss !== 0
                  ? `${stats.totalProfitLoss > 0 ? "+" : ""}${Math.round(stats.totalProfitLoss / 10000)}만`
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
            <EmptyCard
              compact
              title={isFiltered ? "해당 계좌의 거래 기록이 없어요" : "거래 기록이 없습니다"}
              description={isFiltered ? "다른 계좌를 선택해보세요" : undefined}
            />
          ) : (
            <div className="space-y-6">
              {grouped.map(([dateKey, dayTrades]) => (
                <div key={dateKey}>
                  <p className="text-[13px] font-semibold text-muted-foreground mb-2">
                    {formatDateLabel(dateKey)}
                  </p>
                  <div className="space-y-2">
                    {dayTrades.map((trade) => (
                      <TradeCard key={trade.id} trade={trade} meta={stockMeta} onPress={onTradePress} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 하단 매수/매도 액션바 — 매도는 보유 수량이 0이면 비활성 */}
      {(onBuy || onSell) && (
        <FullScreenPanelFooter>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onBuy}
              className={cn(
                "h-12 flex-1 rounded-xl text-[16px] font-bold text-white transition-transform active:scale-[0.98]",
                PNL_COLORS.rise.bg,
              )}
            >
              매수
            </button>
            <button
              type="button"
              onClick={onSell}
              disabled={holdingQuantity <= 0}
              className={cn(
                "h-12 flex-1 rounded-xl text-[16px] font-bold text-white transition-transform active:scale-[0.98]",
                "disabled:opacity-40 disabled:active:scale-100",
                PNL_COLORS.fall.bg,
              )}
            >
              매도
            </button>
          </div>
          {holdingQuantity <= 0 && (
            <p className="mt-2 text-center text-[12px] text-muted-foreground">
              보유 종목이 없어 매도할 수 없어요
            </p>
          )}
        </FullScreenPanelFooter>
      )}
    </>
  );
}
