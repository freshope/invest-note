"use client";

import { useMemo } from "react";
import { HoldingCard } from "./HoldingCard";
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import { useOpenStock } from "@/hooks/useOpenStock";
import { useStockMeta, isMetaCode } from "@/hooks/useStockMeta";
import type { Position } from "@/lib/portfolio";

interface HoldingsListProps {
  positions: Position[];
}

export function HoldingsList({ positions }: HoldingsListProps) {
  const { openStock } = useDetailPanel();
  const openStockByPosition = useOpenStock(openStock, "holdings");

  // evaluation 은 이미 KRW(단일 통화)라 그대로 내림차순 정렬(US 가 환율 반영돼 올바른 순위).
  const sorted = useMemo(
    () => [...positions].sort((a, b) => (b.evaluation ?? 0) - (a.evaluation ?? 0)),
    [positions],
  );

  // 보이는 KR/US 종목 코드를 한 번에 모아 배치 조회 (카드별 N+1 방지).
  const codes = useMemo(
    () => sorted.filter((p) => isMetaCode(p.ticker, p.country)).map((p) => p.ticker),
    [sorted],
  );
  const { meta } = useStockMeta(codes);

  if (sorted.length === 0) return null;

  return (
    <div className="px-5 space-y-2">
      {sorted.map((pos) => (
        <HoldingCard
          key={pos.key}
          position={pos}
          meta={meta[pos.ticker]}
          onPress={openStockByPosition}
        />
      ))}
    </div>
  );
}
