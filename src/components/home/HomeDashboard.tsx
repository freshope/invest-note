"use client";

import { useEffect, useState, useCallback } from "react";
import { DashboardSummary } from "./DashboardSummary";
import { AllocationTabs } from "./AllocationTabs";
import { HoldingsList } from "./HoldingsList";
import { EmptyState } from "./EmptyState";
import type { DashboardTotals, Position, AccountSnapshot } from "@/lib/portfolio";

interface SummaryData {
  totals: DashboardTotals;
  positions: Position[];
  snapshots: AccountSnapshot[];
  hasAccounts: boolean;
  hasTrades: boolean;
}

function Skeleton() {
  return (
    <div className="px-5 pt-5 space-y-4 animate-pulse">
      <div className="space-y-2">
        <div className="h-4 w-16 rounded-md bg-muted" />
        <div className="h-9 w-48 rounded-md bg-muted" />
        <div className="h-3 w-56 rounded-md bg-muted" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-2xl bg-muted/60 p-3.5 space-y-1.5">
            <div className="h-3 w-12 rounded bg-muted" />
            <div className="h-4 w-16 rounded bg-muted" />
          </div>
        ))}
      </div>
      <div className="rounded-2xl bg-muted/60 h-64" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-2xl bg-muted/60 h-28" />
      ))}
    </div>
  );
}

export function HomeDashboard() {
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refetch = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetch("/api/portfolio/summary")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: SummaryData) => setData(d))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  // 거래 수정/삭제 후 다른 컴포넌트(StockDetailPanel 등)에서 발생시키는 이벤트 수신
  useEffect(() => {
    window.addEventListener("portfolio:refresh", refetch);
    return () => window.removeEventListener("portfolio:refresh", refetch);
  }, [refetch]);

  if (loading) return <Skeleton />;

  if (error) {
    return (
      <div className="px-5 pt-10 text-center space-y-3">
        <p className="text-[13px] text-muted-foreground">데이터를 불러오지 못했어요.</p>
        <button
          type="button"
          onClick={refetch}
          className="text-[13px] font-semibold text-foreground underline underline-offset-2"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (!data) return null;

  const { totals, positions, snapshots, hasAccounts, hasTrades } = data;

  if (!hasAccounts) {
    return (
      <div className="pt-10">
        <EmptyState variant="no-accounts" />
      </div>
    );
  }

  if (!hasTrades) {
    return (
      <div className="pt-6 space-y-5">
        <DashboardSummary totals={totals} />
        <EmptyState variant="no-trades" />
      </div>
    );
  }

  return (
    <div className="pb-6 space-y-5">
      <DashboardSummary totals={totals} />
      <AllocationTabs positions={positions} snapshots={snapshots} />

      {positions.length > 0 && (
        <div className="space-y-2">
          <p className="px-5 text-[13px] font-semibold text-muted-foreground">보유 종목</p>
          <HoldingsList positions={positions} />
        </div>
      )}
    </div>
  );
}
