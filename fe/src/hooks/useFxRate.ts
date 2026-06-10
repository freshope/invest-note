"use client";

import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// 환율은 시세보다 느리게 변하므로 길게 캐시(10분).
const FX_STALE_TIME_MS = 600_000;

/**
 * USD/KRW 환율 조회 — KRW 환산 합산 overlay 용. `enabled=false`(해외 보유 없음)면 비활성.
 * - usdkrw: 환율 숫자(없으면 null) — overlay 함수의 usdkrw 인자에 그대로 전달한다.
 * - asOf: 환율 기준 시각(ISO, 없으면 null) — 환산 기준 투명성 표시용.
 */
export function useFxRate(enabled: boolean, base = "USD", quote = "KRW") {
  const { data } = useQuery({
    queryKey: queryKeys.fxRate(base, quote),
    queryFn: () => stocksApi.fx(base, quote),
    enabled,
    staleTime: FX_STALE_TIME_MS,
  });
  return { usdkrw: data?.rate ?? null, asOf: data?.as_of ?? null };
}
