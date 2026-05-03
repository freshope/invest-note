"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { portfolioApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { QUERY_PORTFOLIO_STALE_TIME_MS } from "@/lib/constants/query";

export function usePortfolioSummary() {
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: queryKeys.portfolioSummary,
    queryFn: portfolioApi.summary,
    staleTime: QUERY_PORTFOLIO_STALE_TIME_MS,
  });

  const refetch = useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolioSummary }),
    [queryClient]
  );

  return { data: data ?? null, loading: isPending, error: isError, refetch };
}
