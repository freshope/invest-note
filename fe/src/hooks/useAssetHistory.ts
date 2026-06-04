"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { assetsApi } from "@/lib/api-client";
import type { AssetHistoryResponse } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { QUERY_PORTFOLIO_STALE_TIME_MS } from "@/lib/constants/query";

export interface UseAssetHistoryParams {
  accountId?: string | null;
  ticker?: string | null;
  country?: string | null;
}

/**
 * 일별 자산 변화 조회. usePortfolioSummary 와 동일하게
 * keepPreviousData(필터 전환 시 이전 응답 유지) + portfolio staleTime 을 따른다.
 * 종가는 일별이라 자주 변하지 않고, 거래 등록/수정 시 invalidate 가 보장된다.
 */
export function useAssetHistory({
  accountId = null,
  ticker = null,
  country = null,
}: UseAssetHistoryParams) {
  const { data, isPending, isError, isPlaceholderData, refetch } =
    useQuery<AssetHistoryResponse>({
      queryKey: queryKeys.assetHistory(accountId, ticker),
      queryFn: () => assetsApi.history({ accountId, ticker, country }),
      staleTime: QUERY_PORTFOLIO_STALE_TIME_MS,
      placeholderData: keepPreviousData,
    });

  return {
    data: data ?? null,
    loading: isPending,
    reloading: isPlaceholderData,
    error: isError,
    refetch,
  };
}
