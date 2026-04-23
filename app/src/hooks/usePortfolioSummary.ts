"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { portfolioApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function usePortfolioSummary() {
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: queryKeys.portfolioSummary,
    queryFn: portfolioApi.summary,
  });

  const refetch = useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
    [queryClient]
  );

  return { data: data ?? null, loading: isPending, error: isError, refetch };
}
