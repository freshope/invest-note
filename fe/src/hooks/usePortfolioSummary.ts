"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { portfolioApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { QUERY_PORTFOLIO_STALE_TIME_MS } from "@/lib/constants/query";

export function usePortfolioSummary(accountId: string | null = null) {
  const queryClient = useQueryClient();

  // 칩 전환(=accountId 변경) 시 이전 응답을 유지해 스켈레톤 깜박임 방지.
  const { data, isPending, isError } = useQuery({
    queryKey: queryKeys.portfolioSummary(accountId),
    queryFn: () => portfolioApi.summary(accountId),
    staleTime: QUERY_PORTFOLIO_STALE_TIME_MS,
    placeholderData: keepPreviousData,
  });

  const refetch = useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
    [queryClient]
  );

  return { data: data ?? null, loading: isPending, error: isError, refetch };
}
