"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { portfolioApi } from "@/lib/api-client";

export function usePortfolioSummary() {
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["portfolio", "summary"],
    queryFn: portfolioApi.summary,
  });

  const refetch = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["portfolio"] }),
    [queryClient]
  );

  return { data: data ?? null, loading: isPending, error: isError, refetch };
}
