"use client";

import { useQuery } from "@tanstack/react-query";
import { DashboardTitle, DashboardBody } from "./DashboardSummary";
import { AllocationTabs } from "./AllocationTabs";
import { HoldingsList } from "./HoldingsList";
import { EmptyState } from "./EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { PullToRefresh } from "@/components/shared/PullToRefresh";
import { AccountFilter } from "@/components/shared/AccountFilter";
import {
  useAccountFilter,
  useEffectiveAccountId,
} from "@/components/providers/AccountFilterProvider";
import { usePortfolioSummary } from "@/hooks/usePortfolioSummary";
import { accountsApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

function HeaderSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      <div className="h-4 w-16 rounded-md bg-muted" />
      <div className="h-9 w-48 rounded-md bg-muted" />
      <div className="h-3 w-56 rounded-md bg-muted" />
    </div>
  );
}

function BodySkeleton() {
  return (
    <div className="px-5 pt-2 pb-6 space-y-4 animate-pulse">
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
  const { data: accounts = [] } = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: accountsApi.list,
  });
  const { setSelectedAccountId } = useAccountFilter();
  const effectiveAccountId = useEffectiveAccountId(accounts);
  const { data, loading, error, refetch } = usePortfolioSummary(effectiveAccountId);

  const showFilter = accounts.length >= 2;

  const renderHeaderInner = () => {
    if (loading || error || !data) return <HeaderSkeleton />;
    return <DashboardTitle totals={data.totals} />;
  };

  const renderBody = () => {
    if (loading) return <BodySkeleton />;
    if (error) return <ErrorState onRetry={refetch} />;
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
        <div className="pt-2 space-y-5">
          <DashboardBody totals={totals} />
          <EmptyState variant="no-trades" />
        </div>
      );
    }

    return (
      <div className="pt-2 pb-6 space-y-5">
        <DashboardBody totals={totals} />
        <AllocationTabs positions={positions} snapshots={snapshots} />
        {positions.length > 0 && (
          <div className="space-y-2">
            <p className="px-5 text-[13px] font-semibold text-muted-foreground">보유 종목</p>
            <HoldingsList positions={positions} />
          </div>
        )}
      </div>
    );
  };

  return (
    <PullToRefresh onRefresh={refetch}>
      {/* records 와 동일하게 PageHeader + AccountFilter 를 같은 sticky 컨테이너로 묶는다. */}
      <div className="sticky top-0 z-10 bg-background">
        <PageHeader sticky={false}>{renderHeaderInner()}</PageHeader>
        {showFilter && (
          <AccountFilter
            accounts={accounts}
            value={effectiveAccountId}
            onChange={setSelectedAccountId}
          />
        )}
      </div>
      {renderBody()}
    </PullToRefresh>
  );
}
