"use client";

import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  useSnapshotWhileOpen,
} from "@/components/base/FullScreenPanel";
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
  const queryClient = useQueryClient();
  const router = useRouter();
  const [stockOpen, setStockOpen] = useState(false);

  const handleClose = useCallback(() => onOpenChange(false), [onOpenChange]);

  const handleDeleted = useCallback(() => {
    onOpenChange(false);
    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    router.refresh(); // Server Component 거래 목록 갱신
  }, [onOpenChange, queryClient, router]);

  const handleSaved = useCallback(() => {
    onOpenChange(false);
    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    router.refresh(); // Server Component 거래 목록 갱신
  }, [onOpenChange, queryClient, router]);

  const handleStockPress = trade.ticker_symbol
    ? () => setStockOpen(true)
    : undefined;

  const stockSnap = useSnapshotWhileOpen(stockOpen, { trade, allTrades, accounts });

  return (
    <>
      <FullScreenPanel open={open} onOpenChange={handleClose}>
        <FullScreenPanelContent className="overflow-y-auto">
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

      {stockSnap.trade.ticker_symbol && (
        <StockDetailPanel
          open={stockOpen}
          onOpenChange={setStockOpen}
          assetName={stockSnap.trade.asset_name}
          ticker={stockSnap.trade.ticker_symbol}
          country={stockSnap.trade.country_code ?? "KR"}
          allTrades={stockSnap.allTrades}
          accounts={stockSnap.accounts}
        />
      )}
    </>
  );
}
