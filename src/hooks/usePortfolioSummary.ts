"use client";

import { useEffect, useState, useCallback } from "react";
import type { DashboardTotals, Position, AccountSnapshot } from "@/lib/portfolio";

interface SummaryData {
  totals: DashboardTotals;
  positions: Position[];
  snapshots: AccountSnapshot[];
  hasAccounts: boolean;
  hasTrades: boolean;
}

export function usePortfolioSummary() {
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refetch = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetch("/api/portfolio/summary")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: SummaryData) => { if (!cancelled) { setData(d); setError(false); } })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  useEffect(() => {
    window.addEventListener("portfolio:refresh", refetch);
    return () => window.removeEventListener("portfolio:refresh", refetch);
  }, [refetch]);

  return { data, loading, error, refetch };
}
