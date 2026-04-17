"use client";

import { useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
} from "@/components/common/full-screen-panel";
import { StockDetail } from "./StockDetail";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

// 순환 참조 방지를 위해 dynamic import
import dynamic from "next/dynamic";
const TradeDetailPanel = dynamic(() =>
  import("@/components/records/TradeDetailPanel").then((m) => m.TradeDetailPanel)
);

interface StockDetailPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assetName: string;
  ticker: string;
  country: string;
  allTrades: TradeWithAccount[];
  accounts: Account[];
}

export function StockDetailPanel({
  open,
  onOpenChange,
  assetName,
  ticker,
  country,
  allTrades,
  accounts,
}: StockDetailPanelProps) {
  const router = useRouter();
  const [selectedTrade, setSelectedTrade] = useState<TradeWithAccount | null>(null);
  const [tradeDetailOpen, setTradeDetailOpen] = useState(false);

  const handleClose = useCallback(() => onOpenChange(false), [onOpenChange]);

  const filteredTrades = useMemo(
    () => allTrades.filter(
      (t) => t.ticker_symbol === ticker && (t.country_code ?? "KR") === country
    ),
    [allTrades, ticker, country]
  );

  const stats = useMemo(() => {
    const sellTrades = filteredTrades.filter((t) => t.trade_type === "SELL");
    const winCount = sellTrades.filter((t) => t.result === "SUCCESS").length;
    const totalProfitLoss = sellTrades.reduce(
      (sum, t) => sum + (t.profit_loss ? Number(t.profit_loss) : 0),
      0
    );
    return {
      totalTrades: filteredTrades.length,
      sellCount: sellTrades.length,
      winCount,
      totalProfitLoss,
    };
  }, [filteredTrades]);

  const handleTradePress = useCallback((trade: TradeWithAccount) => {
    setSelectedTrade(trade);
    setTradeDetailOpen(true);
  }, []);

  const handleTradeDetailClose = useCallback((open: boolean) => {
    setTradeDetailOpen(open);
    if (!open) {
      setSelectedTrade(null);
      router.refresh();
      window.dispatchEvent(new CustomEvent("portfolio:refresh"));
    }
  }, [router]);

  return (
    <>
      <FullScreenPanel open={open} onOpenChange={handleClose}>
        <FullScreenPanelContent open={open} className="overflow-y-auto">
          <StockDetail
            assetName={assetName}
            ticker={ticker}
            country={country}
            trades={filteredTrades}
            stats={stats}
            onBack={handleClose}
            onTradePress={handleTradePress}
          />
        </FullScreenPanelContent>
      </FullScreenPanel>

      {tradeDetailOpen && selectedTrade && (
        <TradeDetailPanel
          open={tradeDetailOpen}
          onOpenChange={handleTradeDetailClose}
          trade={selectedTrade}
          accounts={accounts}
          allTrades={allTrades}
        />
      )}
    </>
  );
}
