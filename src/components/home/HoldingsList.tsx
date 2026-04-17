"use client";

import { useState, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import { HoldingCard } from "./HoldingCard";
import type { Position } from "@/lib/portfolio";
import type { TradeWithAccount } from "@/lib/trade-utils";
import type { Account } from "@/types/database";

const StockDetailPanel = dynamic(
  () => import("@/components/stocks/StockDetailPanel").then((m) => m.StockDetailPanel),
  { ssr: false },
);

interface HoldingsListProps {
  positions: Position[];
}

export function HoldingsList({ positions }: HoldingsListProps) {
  const [selected, setSelected] = useState<Position | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [stockTrades, setStockTrades] = useState<TradeWithAccount[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [fetching, setFetching] = useState(false);

  const sorted = useMemo(
    () => [...positions].sort((a, b) => (b.evaluation ?? 0) - (a.evaluation ?? 0)),
    [positions],
  );

  const handleCardPress = useCallback(async (pos: Position) => {
    if (fetching) return;
    setFetching(true);
    setSelected(pos);
    try {
      const res = await fetch(
        `/api/trades?ticker=${encodeURIComponent(pos.ticker)}&country=${encodeURIComponent(pos.country)}`,
      );
      if (res.ok) {
        const { trades, accounts: accs } = await res.json();
        setStockTrades(trades);
        setAccounts(accs);
      } else {
        setStockTrades([]);
        setAccounts([]);
      }
    } catch {
      setStockTrades([]);
      setAccounts([]);
    } finally {
      setFetching(false);
    }
    setPanelOpen(true);
  }, [fetching]);

  const handleOpenChange = useCallback((open: boolean) => {
    setPanelOpen(open);
    if (!open) {
      setSelected(null);
      setStockTrades([]);
    }
  }, []);

  if (sorted.length === 0) return null;

  return (
    <>
      <div className="px-5 space-y-2">
        {sorted.map((pos) => (
          <HoldingCard
            key={pos.key}
            position={pos}
            onPress={() => handleCardPress(pos)}
          />
        ))}
      </div>

      {selected && (
        <StockDetailPanel
          open={panelOpen}
          onOpenChange={handleOpenChange}
          assetName={selected.assetName}
          ticker={selected.ticker}
          country={selected.country}
          allTrades={stockTrades}
          accounts={accounts}
        />
      )}
    </>
  );
}
