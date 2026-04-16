"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
} from "@/components/common/full-screen-panel";
import { TradeDetail } from "./TradeDetail";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

// StockDetailPanel은 순환 참조를 피하기 위해 dynamic import
import dynamic from "next/dynamic";
const StockDetailPanel = dynamic(() =>
  import("@/components/stocks/StockDetailPanel").then((m) => m.StockDetailPanel)
);

interface TradeDetailPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: TradeWithAccount;
  accounts: Account[];
  allTrades: TradeWithAccount[];
}

export function TradeDetailPanel({
  open,
  onOpenChange,
  trade,
  accounts,
  allTrades,
}: TradeDetailPanelProps) {
  const router = useRouter();
  const [stockOpen, setStockOpen] = useState(false);

  const handleClose = useCallback(() => onOpenChange(false), [onOpenChange]);

  const handleDeleted = useCallback(() => {
    onOpenChange(false);
    router.refresh();
  }, [onOpenChange, router]);

  const handleSaved = useCallback(() => {
    onOpenChange(false);
    router.refresh();
  }, [onOpenChange, router]);

  const handleStockPress = trade.ticker_symbol
    ? () => setStockOpen(true)
    : undefined;

  return (
    <>
      <FullScreenPanel open={open} onOpenChange={handleClose}>
        <FullScreenPanelContent open={open} className="overflow-y-auto">
          <TradeDetail
            trade={trade}
            accounts={accounts}
            onBack={handleClose}
            onDeleted={handleDeleted}
            onSaved={handleSaved}
            onStockPress={handleStockPress}
          />
        </FullScreenPanelContent>
      </FullScreenPanel>

      {stockOpen && trade.ticker_symbol && (
        <StockDetailPanel
          open={stockOpen}
          onOpenChange={setStockOpen}
          assetName={trade.asset_name}
          ticker={trade.ticker_symbol}
          country={trade.country_code ?? "KR"}
          allTrades={allTrades}
          accounts={accounts}
        />
      )}
    </>
  );
}
