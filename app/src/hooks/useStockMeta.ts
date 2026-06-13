"use client";

import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api-client";
import type { StockMetaMap } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// 메타는 일단위 갱신 — 시세(45s)보다 훨씬 길게 캐시한다.
const META_STALE_TIME_MS = 10 * 60_000;
const EMPTY_META: StockMetaMap = {};

const KR_CODE_RE = /^\d{6}$/;
// US 티커: 알파벳 시작 + 점(BRK.B)·달러(BAC$B) 허용. 선두 [A-Z] 가 6자리 숫자를
// 배제하므로 KR 6자리 ↔ US 비숫자 disjoint 가정과 정합한다.
const US_TICKER_RE = /^[A-Z][A-Z.$]*$/;

/**
 * 메타 조회 대상인지 — KR 6자리 종목코드 또는 US 티커(점/달러 포함). portfolio.ts 가
 * ticker 없는 포지션에 한글명을 ticker 로 채우므로, 가비지 코드를 BE 로 보내지 않도록
 * 호출 전 필터에 쓴다. /stocks/meta 는 국가 무분기 단일 쿼리라 KR/US 혼재 전송 가능.
 */
export function isMetaCode(
  code: string | null | undefined,
  country: string | null | undefined,
): code is string {
  if (!code) return false;
  if (country === "KR" && KR_CODE_RE.test(code)) return true;
  if (country === "US" && US_TICKER_RE.test(code)) return true;
  return false;
}

/**
 * 종목 코드 목록으로 /stocks/meta 를 배치 조회한다(마켓/시총순위/연금 뱃지용).
 * 호출 전 KR 6자리 또는 US 티커로 필터해 넘긴다. codes 빈 배열이면 비활성 + 빈 객체 반환.
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
