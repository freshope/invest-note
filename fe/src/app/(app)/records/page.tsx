"use client";

import { useQuery } from "@tanstack/react-query";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { TradeList } from "@/components/records/TradeList";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { PullToRefresh } from "@/components/shared/PullToRefresh";

function Skeleton() {
  return (
    <>
      <PageHeader title="기록" />
      <div className="px-5 pt-2 pb-6 space-y-3 animate-pulse">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="rounded-2xl bg-muted/60 h-28" />
        ))}
      </div>
    </>
  );
}

export default function RecordsPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.trades,
    queryFn: () => tradesApi.list(),
  });

  const content = () => {
    if (isLoading) return <Skeleton />;

    if (isError) {
      return (
        <>
          <PageHeader title="기록" />
          <ErrorState onRetry={refetch} />
        </>
      );
    }

    return <TradeList trades={data?.trades ?? []} accounts={data?.accounts ?? []} />;
  };

  return <PullToRefresh onRefresh={refetch}>{content()}</PullToRefresh>;
}
