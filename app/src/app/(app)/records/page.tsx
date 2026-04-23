"use client";

import { useQuery } from "@tanstack/react-query";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { TradeList } from "@/components/records/TradeList";
import { PageHeader } from "@/components/layout/PageHeader";

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

  if (isLoading) return <Skeleton />;

  if (isError) {
    return (
      <>
        <PageHeader title="기록" />
        <div className="px-5 pt-6 text-center space-y-3">
          <p className="text-[13px] text-muted-foreground">데이터를 불러오지 못했어요.</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="text-primary text-[13px] font-medium"
          >
            다시 시도
          </button>
        </div>
      </>
    );
  }

  return <TradeList trades={data?.trades ?? []} accounts={data?.accounts ?? []} />;
}
