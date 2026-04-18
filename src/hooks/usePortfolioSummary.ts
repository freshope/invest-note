"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type { DashboardTotals, Position, AccountSnapshot } from "@/lib/portfolio";

interface SummaryData {
  totals: DashboardTotals;
  positions: Position[];
  snapshots: AccountSnapshot[];
  hasAccounts: boolean;
  hasTrades: boolean;
}

async function fetchPortfolioSummary(): Promise<SummaryData> {
  const res = await fetch("/api/portfolio/summary");
  if (!res.ok) throw new Error("portfolio fetch failed");
  return res.json();
}

export function usePortfolioSummary() {
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["portfolio", "summary"],
    queryFn: fetchPortfolioSummary,
  });

  const refetch = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["portfolio"] }),
    [queryClient]
  );

  return { data: data ?? null, loading: isPending, error: isError, refetch };
}
