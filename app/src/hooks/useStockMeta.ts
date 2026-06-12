"use client";

import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api-client";
import type { StockMetaMap } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// 메타는 일단위 갱신 — 시세(45s)보다 훨씬 길게 캐시한다.
const META_STALE_TIME_MS = 10 * 60_000;
const EMPTY_META: StockMetaMap = {};

const KR_CODE_RE = /^\d{6}$/;

/**
 * 메타 조회 대상인지 — KR 6자리 종목코드만. portfolio.ts 가 ticker 없는 포지션에
 * 한글명을 ticker 로 채우므로, 가비지 코드를 BE 로 보내지 않도록 호출 전 필터에 쓴다.
 */
export function isKrStockCode(
  code: string | null | undefined,
  country: string | null | undefined,
): code is string {
  return country === "KR" && !!code && KR_CODE_RE.test(code);
}

/**
 * 종목 코드 목록으로 /stocks/meta 를 배치 조회한다(마켓/시총순위/연금 뱃지용).
 * 호출 전 KR 6자리 코드로 필터해 넘긴다. codes 빈 배열이면 비활성 + 빈 객체 반환.
 * useQuotes 와 동일하게 응답을 변환 없이 통과시킨다(snake_case 키 유지).
 */
export function useStockMeta(codes: string[]) {
  const enabled = codes.length > 0;

  const { data } = useQuery({
    queryKey: queryKeys.stockMeta(codes),
    queryFn: () => stocksApi.meta(codes.join(",")),
    enabled,
    staleTime: META_STALE_TIME_MS,
  });

  return { meta: data ?? EMPTY_META };
}
