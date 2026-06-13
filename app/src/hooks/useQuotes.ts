"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { stocksApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { QuoteMap } from "@/lib/portfolio";

const QUOTES_STALE_TIME_MS = 45_000;
const EMPTY_QUOTES: QuoteMap = {};

/**
 * 옵션 B: 보유 종목 key 목록으로 /stocks/quote 를 병렬 조회한다.
 * portfolio 요약(lite)과 독립된 쿼리 — 도착하는 대로 평가 값을 overlay 한다.
 * keys 빈 배열이면 비활성(enabled:false) + 빈 객체 반환.
 */
export function useQuotes(keys: string[]) {
  const queryClient = useQueryClient();
  const enabled = keys.length > 0;

  const { data, isError } = useQuery({
    queryKey: queryKeys.quotes(keys),
    queryFn: () => stocksApi.quote(keys.join(",")),
    enabled,
    staleTime: QUOTES_STALE_TIME_MS,
  });

  // pull-to-refresh: refresh=1 로 BE 시세 캐시를 우회해 최신값을 받고 같은 키에 덮어쓴다.
  // staleTime:0 으로 전역 기본 staleTime 에 막히지 않고 항상 네트워크를 탄다.
  const refetch = useCallback(() => {
    if (keys.length === 0) return Promise.resolve(EMPTY_QUOTES);
    return queryClient.fetchQuery({
      queryKey: queryKeys.quotes(keys),
      queryFn: () => stocksApi.quote(keys.join(","), true),
      staleTime: 0,
    });
  }, [queryClient, keys]);

  return {
    quotes: data ?? EMPTY_QUOTES,
    error: isError,
    refetch,
  };
}
