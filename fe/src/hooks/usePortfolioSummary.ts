"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { portfolioApi, type PortfolioSummaryResponse } from "@/lib/api-client";
import { currencyForCountry } from "@/lib/format";
import type { Position } from "@/lib/portfolio";
import { queryKeys } from "@/lib/query-keys";
import { QUERY_PORTFOLIO_STALE_TIME_MS } from "@/lib/constants/query";

/**
 * 버전 스큐(신 FE + 구 BE) 정규화 — 구 BE 의 /portfolio/summary positions 에는 이번에 추가된
 * currency/avgBuyPriceNative/costBasisNative/evaluationNative 가 없다. 소비 지점마다 ?? 가드를
 * 뿌리는 대신 경계에서 1회 정규화해 타입상 non-optional 필드를 채운다. 신 BE 응답은 무변경.
 * (입력 타입은 신규 필드가 없을 수 있으므로 Partial 로 다룬다.)
 */
function normalizePosition(p: Partial<Position> & { country: string }): Position {
  return {
    ...(p as Position),
    currency: p.currency ?? currencyForCountry(p.country),
    avgBuyPriceNative: p.avgBuyPriceNative ?? p.avgBuyPrice ?? 0,
    costBasisNative: p.costBasisNative ?? p.costBasis ?? 0,
    evaluationNative: p.evaluationNative ?? p.evaluation ?? null,
  };
}

export function normalizePortfolioSummary(data: PortfolioSummaryResponse): PortfolioSummaryResponse {
  return {
    ...data,
    positions: (data.positions ?? []).map((p) => normalizePosition(p)),
  };
}

export function usePortfolioSummary(accountId: string | null = null) {
  const queryClient = useQueryClient();

  // 칩 전환(=accountId 변경) 시 이전 응답을 유지해 헤더 count-up의 시작 값을 제공한다.
  // 본문은 isPlaceholderData(=reloading)로 스켈레톤을 띄운다.
  // 옵션 B: 요약은 시세 없이 즉시 응답(withQuotes=false). 시세는 useQuotes 가 병렬 조회해
  // overlay 한다. summary 의 freshness(거래/계좌 변경 반영)는 staleTime 기반 refetch 가 담당.
  const { data, isPending, isError, isPlaceholderData } = useQuery({
    queryKey: queryKeys.portfolioSummary(accountId),
    queryFn: () => portfolioApi.summary(accountId, false, false),
    select: normalizePortfolioSummary,
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
