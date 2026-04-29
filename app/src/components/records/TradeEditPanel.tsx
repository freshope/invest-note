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
  FullScreenPanelFooter,
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
} from "@/lib/constants/trading";
import { PNL_COLORS } from "@/lib/constants/colors";
import { AutoEmotionField, AutoReasoningTagsField } from "./AutoMetaField";
import { getQuantityUnit, CompactRow, CountryBadge, MarketTypeBadge, ExchangeBadge } from "./trade-display";
import { fmt, fmtNumberInput, parseNumberInput } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Trade, Account, ReasoningTag } from "@/types/database";
import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { TradeFreeTextField } from "./TradeFreeTextField";

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

  const { data: summary } = useQuery({
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
        // SELL의 emotion / reasoning_tags / result는 백엔드가 자동 산출 — 패치 미포함.
        ...(isSell
          ? {}
          : { emotion: values.emotion, reasoning_tags: values.reasoning_tags, result: values.result }),
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
                <div className={cn("h-1", isSell ? PNL_COLORS.fall.bg : PNL_COLORS.rise.bg)} />
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[20px] font-bold text-foreground">{trade.asset_name}</span>
                    <span className={cn(
                      "text-[12px] font-bold px-2 py-0.5 rounded-md",
                      isSell
                        ? cn(PNL_COLORS.fall.bgSoft, PNL_COLORS.fall.text)
                        : cn(PNL_COLORS.rise.bgSoft, PNL_COLORS.rise.text)
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
                      isSell ? PNL_COLORS.fall.text : PNL_COLORS.rise.text
                    )}>
                      {fmt(liveTotal)}원
                    </p>
                    <p className="text-[12px] text-muted-foreground text-right mt-0.5 tabular-nums">
                      {fmt(livePrice)}원 × {liveQty}{getQuantityUnit(trade.market_type)}
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
                  {isSell ? "매도 이유" : "근거 / 감정"}
                </p>

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
                {isSell ? (
                  <div className="mb-5">
                    <AutoEmotionField emotion={trade.emotion} />
                  </div>
                ) : (
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
                )}

                {/* 분석 태그 */}
                {isSell ? (
                  <div className="mb-5">
                    <AutoReasoningTagsField tags={trade.reasoning_tags} />
                  </div>
                ) : (
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

            <FullScreenPanelFooter>
              <Button type="submit" size="xl" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "저장 중..." : "저장"}
              </Button>
            </FullScreenPanelFooter>
          </form>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
