"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { HoldingCard } from "./HoldingCard";
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import type { Position } from "@/lib/portfolio";

interface HoldingsListProps {
  positions: Position[];
}

export function HoldingsList({ positions }: HoldingsListProps) {
  const { openStock } = useDetailPanel();
  const [fetching, setFetching] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // 언마운트 시 진행 중인 fetch 취소
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const sorted = useMemo(
    () => [...positions].sort((a, b) => (b.evaluation ?? 0) - (a.evaluation ?? 0)),
    [positions],
  );

  const handleCardPress = useCallback(
    async (pos: Position) => {
      if (fetching) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setFetching(true);
      try {
        const res = await fetch(
          `/api/trades?ticker=${encodeURIComponent(pos.ticker)}&country=${encodeURIComponent(pos.country)}`,
          { signal: controller.signal },
        );
        const { trades, accounts } = res.ok
          ? await res.json()
          : { trades: [], accounts: [] };
        openStock({
          assetName: pos.assetName,
          ticker: pos.ticker,
          country: pos.country,
          allTrades: trades,
          accounts,
        });
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        openStock({
          assetName: pos.assetName,
          ticker: pos.ticker,
          country: pos.country,
          allTrades: [],
          accounts: [],
        });
      } finally {
        setFetching(false);
      }
    },
    [fetching, openStock],
  );

  if (sorted.length === 0) return null;

  return (
    <div className="px-5 space-y-2">
      {sorted.map((pos) => (
        <HoldingCard
          key={pos.key}
          position={pos}
          onPress={() => handleCardPress(pos)}
        />
      ))}
    </div>
  );
}
