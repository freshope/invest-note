"use client";

import { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { tradesApi } from "@/lib/api-client";
import { STRATEGIES, EMOTIONS, REASONING_TAGS } from "./constants";
import { buildMarketDisplay, getQuantityUnit, CompactRow, CountryBadge } from "./trade-display";
import { cn } from "@/lib/utils";
import type { Trade, Account, TradeResult, ReasoningTag } from "@/types/database";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

const RESULTS: { value: TradeResult; label: string; color: string }[] = [
  { value: "SUCCESS", label: "수익 ✅", color: "bg-[var(--rise)] text-white border-[var(--rise)]" },
  { value: "FAIL", label: "손실 ❌", color: "bg-[var(--fall)] text-white border-[var(--fall)]" },
  { value: "BREAKEVEN", label: "본전 ➖", color: "bg-muted text-foreground border-border" },
];

const STRATEGY_LABELS: Record<string, string> = {
  SCALPING: "스캘핑",
  SWING: "스윙",
  LONG_TERM: "장기",
  UNKNOWN: "미분류",
};

const ADHERENCE_CONFIG = {
  FOLLOWED: { label: "전략 준수 ✓", className: "text-green-600 bg-green-50 border-green-200" },
  DEVIATED: { label: "전략 이탈 ✗", className: "text-orange-600 bg-orange-50 border-orange-200" },
  UNKNOWN: { label: "분류 불가", className: "text-muted-foreground bg-muted border-border" },
} as const;

function BreakdownRow({ label, amount, prefix }: { label: string; amount: number; prefix?: "+" | "-" }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-[12px] tabular-nums text-foreground">{prefix ?? ""}{amount.toLocaleString("ko-KR")}원</span>
    </div>
  );
}

function fmtNum(n: number | null | undefined): string {
  if (n == null || n === 0) return "";
  return n.toLocaleString("ko-KR");
}

function formatInput(raw: string): string {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const parts = cleaned.split(".");
  const integer = parts[0] || "";
  const decimal = parts.length > 1 ? "." + parts[1] : "";
  if (!integer && !decimal) return "";
  return (integer ? Number(integer).toLocaleString("ko-KR") : "") + decimal;
}

function parseRaw(s: string): number {
  return Number(s.replace(/,/g, "")) || 0;
}

const schema = z.object({
  price_display: z.string(),
  quantity_display: z.string(),
  commission_display: z.string(),
  tax_display: z.string(),
  strategy_type: z.enum(["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"]).nullable(),
  emotion: z.enum(["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]).nullable(),
  reasoning_tags: z.array(z.enum(["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"])),
  result: z.enum(["SUCCESS", "FAIL", "BREAKEVEN"]).nullable(),
  buy_reason: z.string(),
  sell_reason: z.string(),
  reflection_note: z.string(),
  improvement_note: z.string(),
});

type FormValues = z.infer<typeof schema>;

interface TradeEditPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trade: Trade & { account?: Pick<Account, "name" | "broker"> };
  accounts: Account[];
  onSaved?: () => void;
}

export function TradeEditPanel({ open, onOpenChange, trade, accounts, onSaved }: TradeEditPanelProps) {
  const queryClient = useQueryClient();
  const router = useRouter();
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
    defaultValues: {
      price_display: fmtNum(trade.price),
      quantity_display: fmtNum(trade.quantity),
      commission_display: fmtNum(trade.commission),
      tax_display: fmtNum(trade.tax),
      strategy_type: trade.strategy_type ?? null,
      emotion: trade.emotion ?? null,
      reasoning_tags: (trade.reasoning_tags ?? []) as ReasoningTag[],
      result: trade.result ?? null,
      buy_reason: trade.buy_reason ?? "",
      sell_reason: trade.sell_reason ?? "",
      reflection_note: trade.reflection_note ?? "",
      improvement_note: trade.improvement_note ?? "",
    },
  });

  const { data: summary, isPending: summaryLoading } = useQuery({
    queryKey: ["trade-summary", trade.id],
    queryFn: () => tradesApi.summary(trade.id),
    enabled: isSell && open,
  });

  useEffect(() => {
    if (!open) return;
    reset({
      price_display: fmtNum(trade.price),
      quantity_display: fmtNum(trade.quantity),
      commission_display: fmtNum(trade.commission),
      tax_display: fmtNum(trade.tax),
      strategy_type: trade.strategy_type ?? null,
      emotion: trade.emotion ?? null,
      reasoning_tags: (trade.reasoning_tags ?? []) as ReasoningTag[],
      result: trade.result ?? null,
      buy_reason: trade.buy_reason ?? "",
      sell_reason: trade.sell_reason ?? "",
      reflection_note: trade.reflection_note ?? "",
      improvement_note: trade.improvement_note ?? "",
    });
  }, [open, trade, reset]);

  const { reasoning_tags: tags, result, price_display: priceDisplay, quantity_display: quantityDisplay } = watch();
  const livePrice = parseRaw(priceDisplay);
  const liveQty = parseRaw(quantityDisplay);
  const liveTotal = livePrice * liveQty;
  const acc = accounts.find((a) => a.id === trade.account_id);
  const accountDisplay = acc ? `${acc.name}${acc.broker ? ` · ${acc.broker}` : ""}` : "알 수 없는 계좌";

  function toggleTag(tag: ReasoningTag) {
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    setValue("reasoning_tags", next);
  }

  async function onSubmit(values: FormValues) {
    try {
      await tradesApi.update(trade.id, {
        trade_type: trade.trade_type,
        market_type: trade.market_type,
        price: parseRaw(values.price_display),
        quantity: parseRaw(values.quantity_display),
        commission: parseRaw(values.commission_display),
        tax: parseRaw(values.tax_display),
        strategy_type: isSell ? (summary?.strategyEvaluation?.planned ?? null) : values.strategy_type,
        emotion: values.emotion,
        reasoning_tags: values.reasoning_tags,
        result: isSell ? (summary?.result ?? null) : values.result,
        buy_reason: values.buy_reason.trim() || null,
        sell_reason: values.sell_reason.trim() || null,
        reflection_note: values.reflection_note.trim() || null,
        improvement_note: values.improvement_note.trim() || null,
      });
      await queryClient.invalidateQueries({ queryKey: ["trade", trade.id] });
      await queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      router.refresh();
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
            <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
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
                  {trade.ticker_symbol && (
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-mono text-muted-foreground">{trade.ticker_symbol}</span>
                      <CountryBadge countryCode={trade.country_code ?? "KR"} />
                    </div>
                  )}
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
                  <CompactRow label="계좌">{accountDisplay}</CompactRow>
                  <CompactRow label="시장">{buildMarketDisplay(trade)}</CompactRow>
                </div>
              </div>

              {/* 가격 */}
              <div className="space-y-1.5">
                <Label>가격 (원) <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="price_display"
                  render={({ field }) => (
                    <Input type="text" inputMode="numeric" placeholder="0"
                      value={field.value}
                      onChange={(e) => field.onChange(formatInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 수량 */}
              <div className="space-y-1.5">
                <Label>수량 <span className="text-destructive">*</span></Label>
                <Controller
                  control={control}
                  name="quantity_display"
                  render={({ field }) => (
                    <Input type="text" inputMode="decimal" placeholder="0"
                      value={field.value}
                      onChange={(e) => field.onChange(formatInput(e.target.value))}
                    />
                  )}
                />
              </div>

              {/* 수수료 */}
              <div className="space-y-1.5">
                <Label>수수료 (원)</Label>
                <Controller
                  control={control}
                  name="commission_display"
                  render={({ field }) => (
                    <Input type="text" inputMode="numeric" placeholder="0"
                      value={field.value}
                      onChange={(e) => field.onChange(formatInput(e.target.value))}
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
                    name="tax_display"
                    render={({ field }) => (
                      <Input type="text" inputMode="numeric" placeholder="0"
                        value={field.value}
                        onChange={(e) => field.onChange(formatInput(e.target.value))}
                      />
                    )}
                  />
                </div>
              )}

              <div className="border-t border-border pt-4 mt-2">
                <p className="text-[13px] font-semibold text-muted-foreground mb-4">
                  {isSell ? "회고 / 결과" : "근거 / 감정"}
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
                        {summary?.holdingDays != null && (
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[12px] text-muted-foreground">
                              보유 {summary.holdingDays}일
                              {summary.strategyEvaluation && ` · ${STRATEGY_LABELS[summary.strategyEvaluation.actual] ?? summary.strategyEvaluation.actual}`}
                            </span>
                            {summary.strategyEvaluation && summary.strategyEvaluation.adherence !== "UNKNOWN" && (
                              <span className={cn(
                                "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold border",
                                ADHERENCE_CONFIG[summary.strategyEvaluation.adherence].className,
                              )}>
                                {summary.strategyEvaluation.planned && `계획: ${STRATEGY_LABELS[summary.strategyEvaluation.planned] ?? summary.strategyEvaluation.planned} · `}
                                {ADHERENCE_CONFIG[summary.strategyEvaluation.adherence].label}
                              </span>
                            )}
                          </div>
                        )}
                      </>
                    )}
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
                  <div className="space-y-1.5 mb-5">
                    <Label>매수 근거</Label>
                    <Textarea {...register("buy_reason")} placeholder="매수한 근거를 간단히 적어주세요" rows={3} />
                  </div>
                )}

                {/* 매도 이유 */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>매도 이유</Label>
                    <Textarea {...register("sell_reason")} placeholder="왜 매도했나요?" rows={2} />
                  </div>
                )}

                {/* 잘한 점 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>잘한 점 / 배운 점</Label>
                    <Textarea {...register("reflection_note")} placeholder="이번 거래에서 잘한 점이나 배운 것을 기록해보세요" rows={3} />
                  </div>
                )}

                {/* 개선할 점 (매도) */}
                {isSell && (
                  <div className="space-y-1.5 mb-5">
                    <Label>개선할 점 / 다음에는</Label>
                    <Textarea {...register("improvement_note")} placeholder="다음 거래에서 개선하고 싶은 점을 적어주세요" rows={3} />
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
