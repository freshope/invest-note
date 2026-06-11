"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Dialog as DialogPrimitive } from "radix-ui";
import { CheckIcon } from "lucide-react";
import { accountsApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useEffectiveAccountId } from "@/components/providers/AccountFilterProvider";
import { usePortfolioSummary } from "@/hooks/usePortfolioSummary";
import { useQuotes } from "@/hooks/useQuotes";
import { useFxRate } from "@/hooks/useFxRate";
import { CountryBadge } from "@/components/records/trade-display";
import { cn } from "@/lib/utils";
import { DEFAULT_COUNTRY_CODE } from "@/lib/constants/market";
import { mergeQuotes, type Position } from "@/lib/portfolio";

interface StockSwitchSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 현재 보고 있는 종목 key (`${ticker}:${country}`) — 목록에서 강조 표시 */
  currentKey: string;
  onSelect: (position: Position) => void;
}

/**
 * 종목 상세/추이 헤더의 종목명에서 띄우는 보유 종목 전환 바텀시트.
 * 현재 계좌 필터를 존중해 보유 종목을 평가액 내림차순으로 보여준다.
 */
export function StockSwitchSheet({ open, onOpenChange, currentKey, onSelect }: StockSwitchSheetProps) {
  const { data: accounts = [] } = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: accountsApi.list,
  });
  const effectiveAccountId = useEffectiveAccountId(accounts);
  const { data, loading } = usePortfolioSummary(effectiveAccountId);

  // summary(lite) 의 positions 는 시세 미포함(evaluation=null)이라 그대로 정렬하면 no-op.
  // 홈과 동일하게 useQuotes 를 overlay 해 evaluation 을 채운 뒤 평가액 내림차순 정렬한다.
  const basePositions = data?.positions;
  const quoteKeysSig = basePositions
    ? [...basePositions.map((p) => p.key)].sort().join(",")
    : "";
  const quoteKeys = useMemo(
    () => (quoteKeysSig ? quoteKeysSig.split(",") : []),
    [quoteKeysSig],
  );
  const { quotes } = useQuotes(quoteKeys);
  // 해외 보유가 있으면 환율로 KRW 환산해 정렬(native 정렬은 US 가 항상 바닥).
  const hasForeign = (basePositions ?? []).some((p) => p.country !== DEFAULT_COUNTRY_CODE);
  const { usdkrw } = useFxRate(hasForeign);

  const positions = useMemo(() => {
    if (!data) return [];
    // mergeQuotes 가 usdkrw 로 evaluation 을 KRW 환산 → 단일 통화로 정렬(US 도 환율 반영).
    return mergeQuotes(data.positions, quotes, usdkrw).sort(
      (a, b) => (b.evaluation ?? 0) - (a.evaluation ?? 0),
    );
  }, [data, quotes, usdkrw]);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[200] bg-black/30 supports-backdrop-filter:backdrop-blur-xs data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          className="fixed inset-x-0 bottom-0 z-[200] flex max-h-[70vh] flex-col rounded-t-2xl bg-background ring-1 ring-foreground/10 outline-none data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom data-[state=closed]:animate-out data-[state=closed]:slide-out-to-bottom"
          style={{ paddingBottom: "calc(0.5rem + var(--safe-area-inset-bottom, env(safe-area-inset-bottom)))" }}
        >
          {/* 그랩 핸들 */}
          <div className="shrink-0 flex justify-center pt-2.5 pb-1">
            <div className="h-1 w-9 rounded-full bg-muted-foreground/30" aria-hidden />
          </div>
          <DialogPrimitive.Title className="shrink-0 px-5 pb-2 pt-1 text-[15px] font-bold text-foreground">
            종목 변경
          </DialogPrimitive.Title>
          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-2">
            {positions.length === 0 ? (
              loading ? (
                <ul className="space-y-0.5" aria-hidden>
                  {[0, 1, 2, 3].map((i) => (
                    <li key={i} className="px-3 py-3">
                      <div className="h-4 w-32 animate-pulse rounded bg-muted/60" />
                      <div className="mt-1.5 h-3 w-16 animate-pulse rounded bg-muted/60" />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-2 py-8 text-center text-[14px] text-muted-foreground">
                  보유 중인 종목이 없어요
                </p>
              )
            ) : (
              <ul className="space-y-0.5">
                {positions.map((pos) => {
                  const isCurrent = pos.key === currentKey;
                  return (
                    <li key={pos.key}>
                      <button
                        type="button"
                        onClick={() => onSelect(pos)}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-xl px-3 py-3 text-left transition-colors active:bg-muted",
                          isCurrent ? "bg-muted/60" : "hover:bg-muted/40",
                        )}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate text-[15px] font-bold text-foreground">
                              {pos.assetName}
                            </span>
                            <CountryBadge countryCode={pos.country} />
                          </div>
                          <p className="text-[12px] font-mono text-muted-foreground">{pos.ticker}</p>
                        </div>
                        {isCurrent && (
                          <CheckIcon className="size-5 shrink-0 text-[var(--brand)]" strokeWidth={2.4} />
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
