"use client";

import { useEffect, useRef } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { tradesApi } from "@/lib/api-client";
import { VALIDATION_LIMITS, TRADE_FREE_TEXT_ERROR } from "@/lib/constants/validation";
import { queryKeys } from "@/lib/query-keys";
import {
  STRATEGIES,
  EMOTIONS,
  REASONING_TAGS,
  STRATEGY_VALUES,
  EMOTION_VALUES,
  REASONING_TAG_VALUES,
  TRADE_RESULT_VALUES,
} from "./constants";
import { getQuantityUnit, CompactRow, CountryBadge, MarketTypeBadge, ExchangeBadge } from "./trade-display";
import { fmtNumberInput, parseNumberInput } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Trade, Account, ReasoningTag } from "@/types/database";
import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { TradeFreeTextField } from "./TradeFreeTextField";
import { TradeHoldingSection } from "./TradeHoldingSection";

function BreakdownRow({ label, amount, prefix }: { label: string; amount: number; prefix?: "+" | "-" }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-[12px] tabular-nums text-foreground">{prefix ?? ""}{amount.toLocaleString("ko-KR")}원</span>
    </div>
  );
}

const schema = z.object({
  price: z.number().positive("올바른 가격을 입력해주세요."),
  quantity: z.number().positive("올바른 수량을 입력해주세요."),
  commission: z.number().min(0),
  tax: z.number().min(0),
  strategy_type: z.enum(STRATEGY_VALUES).nullable(),
  emotion: z.enum(EMOTION_VALUES).nullable(),
  reasoning_tags: z.array(z.enum(REASONING_TAG_VALUES)),
  result: z.enum(TRADE_RESULT_VALUES).nullable(),
  buy_reason: z.string().max(VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX, TRADE_FREE_TEXT_ERROR),
  sell_reason: z.string().max(VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX, TRADE_FREE_TEXT_ERROR),
});

type FormValues = z.infer<typeof schema>;

function buildFormValues(trade: Trade): FormValues {
  return {
    price: trade.price,
    quantity: trade.quantity,
    commission: trade.commission,
    tax: trade.tax,
    strategy_type: trade.strategy_type ?? null,
    emotion: trade.emotion ?? null,
    reasoning_tags: (trade.reasoning_tags ?? []) as ReasoningTag[],
    result: trade.result ?? null,
    buy_reason: trade.buy_reason ?? "",
    sell_reason: trade.sell_reason ?? "",
  };
}

interface TradeEditPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: Trade & { account?: Pick<Account, "name" | "broker"> };
  accounts: Account[];
  onSaved?: () => void;
}

export function TradeEditPanel({ open, onOpenChange, trade, accounts, onSaved }: TradeEditPanelProps) {
  const queryClient = useQueryClient();
  const isSell = trade.trade_type === "SELL";

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    setError,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: buildFormValues(trade),
  });

  const { data: summary, isPending: summaryLoading } = useQuery({
    queryKey: queryKeys.tradeSummary(trade.id),
    queryFn: () => tradesApi.summary(trade.id),
    enabled: isSell && open,
  });

  // 패널이 열리는 순간에만 reset — 배경 refetch로 trade prop이 바뀌어도 편집 중인 내용을 덮지 않도록.
  const initializedRef = useRef(false);
  useEffect(() => {
    if (!open) {
      initializedRef.current = false;
      return;
    }
    if (initializedRef.current) return;
    initializedRef.current = true;
    reset(buildFormValues(trade));
  }, [open, trade, reset]);

  const {
    reasoning_tags: tags,
    price: livePrice,
    quantity: liveQty,
    buy_reason: buyReason,
    sell_reason: sellReason,
  } = watch();
  const liveTotal = livePrice * liveQty;
  const acc = accounts.find((a) => a.id === trade.account_id);

  function toggleTag(tag: ReasoningTag) {
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    setValue("reasoning_tags", next);
  }

  async function onSubmit(values: FormValues) {
    try {
      await tradesApi.update(trade.id, {
        trade_type: trade.trade_type,
        market_type: trade.market_type,
        price: values.price,
        quantity: values.quantity,
        commission: values.commission,
        tax: values.tax,
        strategy_type: isSell ? (summary?.strategyEvaluation?.planned ?? null) : values.strategy_type,
        emotion: values.emotion,
        reasoning_tags: values.reasoning_tags,
        result: isSell ? (summary?.result ?? null) : values.result,
        buy_reason: values.buy_reason.trim() || null,
        sell_reason: values.sell_reason.trim() || null,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.trade(trade.id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.tradeSummary(trade.id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
        queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
      ]);
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      setError("root", { message: err instanceof Error ? err.message : "저장에 실패했습니다." });
    }
  }

  const firstError = errors.root?.message ?? (Object.values(errors)[0]?.message as string | undefined);

  return (
    <FullScreenPanel open={open} onOpenChange={() => onOpenChange(false)}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title="거래 수정" />
        <FullScreenPanelBody>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
            <div className="flex-1 px-5 pt-5 pb-4 space-y-5">
              {/* 종목 헤더 카드 */}
              <div className="rounded-2xl overflow-hidden bg-muted/60">
                <div className={cn("h-1", isSell ? "bg-[var(--fall)]" : "bg-[var(--rise)]")} />
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[20px] font-bold text-foreground">{trade.asset_name}</span>
                    <span className={cn(
                      "text-[12px] font-bold px-2 py-0.5 rounded-md",
                      isSell
                        ? "bg-[var(--fall)]/10 text-[var(--fall)]"
                        : "bg-[var(--rise)]/10 text-[var(--rise)]"
                    )}>
                      {isSell ? "매도" : "매수"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {trade.ticker_symbol && (
                      <span className="text-[13px] font-mono text-muted-foreground">{trade.ticker_symbol}</span>
                    )}
                    <MarketTypeBadge marketType={trade.market_type} />
                    {trade.market_type === "STOCK" && (
                      <>
                        <CountryBadge countryCode={trade.country_code ?? "KR"} />
                        <ExchangeBadge exchange={trade.exchange} />
                      </>
                    )}
                  </div>
                  <div className="mt-4 pt-4 border-t border-border/40">
                    <p className={cn(
                      "text-[24px] font-bold tabular-nums text-right",
                      isSell ? "text-[var(--fall)]" : "text-[var(--rise)]"
                    )}>
                      {liveTotal.toLocaleString("ko-KR")}원
                    </p>
                    <p className="text-[12px] text-muted-foreground text-right mt-0.5 tabular-nums">
                      {livePrice.toLocaleString("ko-KR")}원 × {liveQty}{getQuantityUnit(trade.market_type)}
                    </p>
                  </div>
                </div>
              </div>

              {/* 기본 거래 정보 */}
              <div className="rounded-2xl bg-muted/60 p-4">
                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <CompactRow label="날짜">
                    {format(new Date(trade.traded_at), "yyyy년 M월 d일 (EEE)", { locale: ko })}
                  </CompactRow>
                  <CompactRow label="계좌">
                    <span className="inline-flex items-center gap-1">
                      {acc?.broker && <BrokerLogo broker={acc.broker} size={16} />}
                      {acc?.name ?? "알 수 없는 계좌"}
                    </span>
                  </CompactRow>
                </div>
              </div>

              {/* 가격 */}
              <div className="space-y-1.5">
                <Label>가격 (원) <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="price"
                  render={({ field }) => (
                    <Input type="text" inputMode="numeric" placeholder="0"
                      value={fmtNumberInput(field.value)}
                      onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 수량 */}
              <div className="space-y-1.5">
                <Label>수량 <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="quantity"
                  render={({ field }) => (
                    <Input type="text" inputMode="decimal" placeholder="0"
                      value={fmtNumberInput(field.value)}
                      onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 수수료 */}
              <div className="space-y-1.5">
                <Label>수수료 (원)</Label>
                <Controller
                  control={control}
                  name="commission"
                  render={({ field }) => (
                    <Input type="text" inputMode="numeric" placeholder="0"
                      value={fmtNumberInput(field.value)}
                      onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 제세금 (매도) */}
              {isSell && (
                <div className="space-y-1.5">
                  <Label>제세금 (원)</Label>
                  <Controller
                    control={control}
                    name="tax"
                    render={({ field }) => (
                      <Input type="text" inputMode="numeric" placeholder="0"
                        value={fmtNumberInput(field.value)}
                        onChange={(e) => field.onChange(parseNumberInput(e.target.value))}
                      />
                    )}
                  />
                </div>
              )}

              <div className="border-t border-border pt-4 mt-2">
                <p className="text-[13px] font-semibold text-muted-foreground mb-4">
                  {isSell ? "매도 이유 / 결과" : "근거 / 감정"}
                </p>

                {/* 자동 계산 요약 카드 (매도) */}
                {isSell && (
                  <div className="rounded-2xl bg-muted/60 p-4 space-y-3 mb-5">
                    <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wide">거래 결과 (자동 계산)</p>
                    {summaryLoading ? (
                      <p className="text-[13px] text-muted-foreground">계산 중...</p>
                    ) : (
                      <>
                        <div className="flex items-center justify-between">
                          <span className={cn(
                            "inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-bold border",
                            summary?.result === "SUCCESS" && "bg-[var(--rise)]/10 text-[var(--rise)] border-[var(--rise)]/30",
                            summary?.result === "FAIL" && "bg-[var(--fall)]/10 text-[var(--fall)] border-[var(--fall)]/30",
                            summary?.result === "BREAKEVEN" && "bg-muted text-foreground border-border",
                            !summary?.result && "bg-muted text-muted-foreground border-border",
                          )}>
                            {summary?.result === "SUCCESS" ? "수익 ✅" : summary?.result === "FAIL" ? "손실 ❌" : summary?.result === "BREAKEVEN" ? "본전 ➖" : "–"}
                          </span>
                          {summary?.pnl != null && (
                            <span className={cn(
                              "text-[16px] font-bold tabular-nums",
                              summary.pnl > 0 && "text-[var(--rise)]",
                              summary.pnl < 0 && "text-[var(--fall)]",
                            )}>
                              {summary.pnl >= 0 ? "+" : ""}{summary.pnl.toLocaleString("ko-KR")}원
                            </span>
                          )}
                        </div>
                        {summary?.breakdown && !summary.breakdown.isManualInput && (
                          <div className="rounded-lg bg-background border border-border/60 px-3 py-2.5 space-y-1.5">
                            <BreakdownRow
                              label={`매도금액 (${summary.breakdown.sellPrice.toLocaleString("ko-KR")}원 × ${summary.breakdown.quantity}주)`}
                              amount={summary.breakdown.sellAmount}
                              prefix="+"
                            />
                            <BreakdownRow
                              label={`매수비용 (평단 ${Math.round(summary.breakdown.avgCostPrice).toLocaleString("ko-KR")}원 × ${summary.breakdown.quantity}주)`}
                              amount={summary.breakdown.costBasis}
                              prefix="-"
                            />
                            {summary.breakdown.commission > 0 && <BreakdownRow label="수수료" amount={summary.breakdown.commission} prefix="-" />}
                            {summary.breakdown.tax > 0 && <BreakdownRow label="세금" amount={summary.breakdown.tax} prefix="-" />}
                            <div className="border-t border-border/60 pt-1.5 flex justify-between items-center">
                              <span className="text-[12px] font-semibold text-foreground">실현손익</span>
                              <span className={cn(
                                "text-[13px] font-bold tabular-nums",
                                summary.pnl != null && summary.pnl > 0 && "text-[var(--rise)]",
                                summary.pnl != null && summary.pnl < 0 && "text-[var(--fall)]",
                              )}>
                                {summary.pnl != null ? `${summary.pnl >= 0 ? "+" : ""}${summary.pnl.toLocaleString("ko-KR")}원` : "–"}
                              </span>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {/* 보유 정보 (매도) */}
                {isSell && (
                  <div className="mb-5">
                    <TradeHoldingSection
                      tradedAt={trade.traded_at}
                      holdingDays={summary?.holdingDays ?? null}
                      strategyEvaluation={summary?.strategyEvaluation ?? null}
                    />
                  </div>
                )}

                {/* 전략 (매수만) */}
                {!isSell && (
                <div className="space-y-2 mb-5">
                  <Label>전략</Label>
                  <Controller
                    control={control}
                    name="strategy_type"
                    render={({ field }) => (
                      <div className="grid grid-cols-4 gap-2">
                        {STRATEGIES.map((s) => (
                          <button key={s.value} type="button"
                            onClick={() => field.onChange(field.value === s.value ? null : s.value)}
                            className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                              field.value === s.value
                                ? "bg-primary text-primary-foreground border-primary"
                                : "border-border bg-muted/50 text-muted-foreground"
                            }`}
                          >{s.label}</button>
                        ))}
                      </div>
                    )}
                  />
                </div>
                )}

                {/* 감정 */}
                <div className="space-y-2 mb-5">
                  <Label>감정</Label>
                  <Controller
                    control={control}
                    name="emotion"
                    render={({ field }) => (
                      <div className="grid grid-cols-3 gap-2">
                        {EMOTIONS.map((e) => (
                          <button key={e.value} type="button"
                            onClick={() => field.onChange(field.value === e.value ? null : e.value)}
                            className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                              field.value === e.value
                                ? "bg-primary text-primary-foreground border-primary"
                                : "border-border bg-muted/50 text-muted-foreground"
                            }`}
                          >{e.label}</button>
                        ))}
                      </div>
                    )}
                  />
                </div>

                {/* 분석 태그 (매수) */}
                {!isSell && (
                  <div className="space-y-2 mb-5">
                    <Label>분석 태그 <span className="text-[12px] font-normal text-muted-foreground">(복수 선택)</span></Label>
                    <div className="grid grid-cols-2 gap-2">
                      {REASONING_TAGS.map((t) => (
                        <button key={t.value} type="button"
                          onClick={() => toggleTag(t.value)}
                          className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                            tags.includes(t.value)
                              ? "bg-primary text-primary-foreground border-primary"
                              : "border-border bg-muted/50 text-muted-foreground"
                          }`}
                        >{t.label}</button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 매수 근거 */}
                {!isSell && (
                  <div className="mb-5">
                    <TradeFreeTextField
                      id="edit_buy_reason"
                      label="매수 근거"
                      valueLength={(buyReason ?? "").length}
                      {...register("buy_reason")}
                      placeholder="매수한 근거를 간단히 적어주세요"
                      rows={3}
                    />
                  </div>
                )}

                {/* 매도 이유 */}
                {isSell && (
                  <div className="mb-5">
                    <TradeFreeTextField
                      id="edit_sell_reason"
                      label="매도 이유"
                      valueLength={(sellReason ?? "").length}
                      {...register("sell_reason")}
                      placeholder="왜 매도했나요?"
                      rows={2}
                    />
                  </div>
                )}

              </div>

              {firstError && <p className="text-sm text-destructive">{firstError}</p>}
            </div>

            <div
              className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
              style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
            >
              <Button type="submit" size="xl" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "저장 중..." : "저장"}
              </Button>
            </div>
          </form>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
