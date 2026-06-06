"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { ChartSplineIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
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
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import { usePortfolioSummary } from "@/hooks/usePortfolioSummary";
import { useQuotes } from "@/hooks/useQuotes";
import { accountsApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import {
  mergeQuotes,
  applyQuotesToTotals,
  applyQuotesToSnapshots,
} from "@/lib/portfolio";

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
  const { openAssetHistory } = useDetailPanel();
  const effectiveAccountId = useEffectiveAccountId(accounts);
  const { data, loading, reloading, error, refetch } =
    usePortfolioSummary(effectiveAccountId);

  // 시세 조회 대상 key 목록 — summary(lite) 의 positions 에서 추출. 정렬 join 을 memo dep 로
  // 써서 매 렌더마다 새 배열이 만들어져도 쿼리 키가 churn 하지 않도록 안정화한다.
  const positions = data?.positions;
  const quoteKeysSig = positions
    ? [...positions.map((p) => p.key)].sort().join(",")
    : "";
  const quoteKeys = useMemo(
    () => (quoteKeysSig ? quoteKeysSig.split(",") : []),
    [quoteKeysSig],
  );

  const { quotes, refetch: refetchQuotes } = useQuotes(quoteKeys);

  // summary(lite) + quotes 결합: 시세 도착 전엔 base(시세 null), 도착하면 overlay 값으로 교체.
  // HoldingCard 가 null→"—" 처리하므로 깜빡임 없이 점진 렌더.
  const view = useMemo(() => {
    if (!data) return null;
    const mergedPositions = mergeQuotes(data.positions, quotes);
    return {
      totals: applyQuotesToTotals(data.totals, mergedPositions),
      positions: mergedPositions,
      snapshots: applyQuotesToSnapshots(data.snapshots, quotes),
      hasAccounts: data.hasAccounts,
      hasTrades: data.hasTrades,
    };
  }, [data, quotes]);

  // pull-to-refresh: 요약(거래/계좌 변경 반영) + 시세(refresh=1) 둘 다 갱신.
  const handleRefresh = () => Promise.all([refetch(), refetchQuotes()]);

  const showFilter = accounts.length >= 2;

  const renderHeaderInner = () => {
    if (loading || error || !view) return <HeaderSkeleton />;
    return <DashboardTitle totals={view.totals} />;
  };

  const renderBody = () => {
    // 초기 로드(loading) + 계좌 필터 전환 재조회(reloading) 모두 스켈레톤.
    // 헤더는 placeholder 숫자를 유지하다 새 데이터 도착 시 count-up 한다.
    if (loading || reloading) return <BodySkeleton />;
    if (error) return <ErrorState onRetry={refetch} />;
    if (!view) return null;

    const { totals, positions, snapshots, hasAccounts, hasTrades } = view;

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
    <PullToRefresh onRefresh={handleRefresh}>
      <div className="sticky top-0 z-10 bg-background">
        <PageHeader sticky={false}>
          {/* 자산 변화 패널 진입 — 기록탭 헤더 액션과 동일 계열(outline sm pill). skeleton swap 과 무관하게 항상 노출.
              다른 패널과 동일한 슬라이드 애니메이션을 위해 라우팅 대신 AssetHistoryPanel 을 연다. */}
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              className="absolute right-0 top-0"
              onClick={() =>
                openAssetHistory({ assetName: null, ticker: null, country: null })
              }
            >
              <ChartSplineIcon />
              자산 추이
            </Button>
            <div className="pr-24">{renderHeaderInner()}</div>
          </div>
        </PageHeader>
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
