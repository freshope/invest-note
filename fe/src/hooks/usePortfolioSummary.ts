"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { portfolioApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { QUERY_PORTFOLIO_STALE_TIME_MS } from "@/lib/constants/query";

export function usePortfolioSummary(accountId: string | null = null) {
  const queryClient = useQueryClient();

  // 칩 전환(=accountId 변경) 시 이전 응답을 유지해 헤더 count-up의 시작 값을 제공한다.
  // 본문은 isPlaceholderData(=reloading)로 스켈레톤을 띄운다.
  const { data, isPending, isError, isPlaceholderData } = useQuery({
    queryKey: queryKeys.portfolioSummary(accountId),
    queryFn: () => portfolioApi.summary(accountId),
    staleTime: QUERY_PORTFOLIO_STALE_TIME_MS,
    placeholderData: keepPreviousData,
  });

  // pull-to-refresh / 에러 재시도: 현재 보고 있는 요약을 refresh=1 로 새로 받아(시세 캐시 우회)
  // 같은 캐시 키에 덮어쓴다. 일반 staleTime 기반 백그라운드 refetch 는 캐시 경로 그대로 사용.
  const refetch = useCallback(
    () =>
      queryClient.fetchQuery({
        queryKey: queryKeys.portfolioSummary(accountId),
        queryFn: () => portfolioApi.summary(accountId, true),
      }),
    [queryClient, accountId]
  );

  return {
    data: data ?? null,
    loading: isPending,
    reloading: isPlaceholderData,
    error: isError,
    refetch,
  };
}
