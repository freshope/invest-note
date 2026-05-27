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
  // 옵션 B: 요약은 시세 없이 즉시 응답(withQuotes=false). 시세는 useQuotes 가 병렬 조회해
  // overlay 한다. summary 의 freshness(거래/계좌 변경 반영)는 staleTime 기반 refetch 가 담당.
  const { data, isPending, isError, isPlaceholderData } = useQuery({
    queryKey: queryKeys.portfolioSummary(accountId),
    queryFn: () => portfolioApi.summary(accountId, false, false),
    staleTime: QUERY_PORTFOLIO_STALE_TIME_MS,
    placeholderData: keepPreviousData,
  });

  // pull-to-refresh / 에러 재시도: 요약을 새로 받아 같은 캐시 키에 덮어쓴다. staleTime:0 으로
  // fetchQuery 가 전역 기본 staleTime 에 막히지 않고 항상 네트워크를 타도록 강제한다.
  // 시세 freshness 는 별도 quote refetch(refresh=1)가 담당하므로 여기선 시세 우회 불필요 →
  // refresh=false. 이 refetch 는 거래/계좌 변경 반영용.
  const refetch = useCallback(
    () =>
      queryClient.fetchQuery({
        queryKey: queryKeys.portfolioSummary(accountId),
        queryFn: () => portfolioApi.summary(accountId, false, false),
        staleTime: 0,
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
