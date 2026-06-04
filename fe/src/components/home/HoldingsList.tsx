"use client";

import { useMemo } from "react";
import { HoldingCard } from "./HoldingCard";
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import { useOpenStock } from "@/hooks/useOpenStock";
import type { Position } from "@/lib/portfolio";

interface HoldingsListProps {
  positions: Position[];
}

export function HoldingsList({ positions }: HoldingsListProps) {
  const { openStock } = useDetailPanel();
  const openStockByPosition = useOpenStock(openStock);

  const sorted = useMemo(
    () => [...positions].sort((a, b) => (b.evaluation ?? 0) - (a.evaluation ?? 0)),
    [positions],
  );

  if (sorted.length === 0) return null;

  return (
    <div className="px-5 space-y-2">
      {sorted.map((pos) => (
        <HoldingCard key={pos.key} position={pos} onPress={openStockByPosition} />
      ))}
    </div>
  );
}
