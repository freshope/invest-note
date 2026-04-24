"use client";

import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { HoldingCard } from "./HoldingCard";
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import { tradesApi, ApiError } from "@/lib/api-client";
import type { Position } from "@/lib/portfolio";

interface HoldingsListProps {
  positions: Position[];
}

export function HoldingsList({ positions }: HoldingsListProps) {
  const { openStock } = useDetailPanel();
  const [fetching, setFetching] = useState(false);

  const sorted = useMemo(
    () => [...positions].sort((a, b) => (b.evaluation ?? 0) - (a.evaluation ?? 0)),
    [positions],
  );

  const handleCardPress = useCallback(
    async (pos: Position) => {
      if (fetching) return;
      setFetching(true);
      try {
        const { trades, accounts } = await tradesApi.list({
          ticker: pos.ticker,
          country: pos.country,
        });
        openStock({
          assetName: pos.assetName,
          ticker: pos.ticker,
          country: pos.country,
          allTrades: trades,
          accounts,
        });
      } catch (err) {
        const toastId = "holdings-fetch-error";
        if (err instanceof ApiError) {
          const msg = err.status === 401
            ? "다시 로그인해 주세요"
            : "보유 종목을 불러오지 못했어요 (서버 오류)";
          toast.error(msg, { id: toastId });
        } else {
          toast.error("네트워크 연결을 확인해 주세요", { id: toastId });
        }
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
