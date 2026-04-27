"use client";

import { useForm, Controller, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { tradesApi } from "@/lib/api-client";
import { VALIDATION_LIMITS, TRADE_FREE_TEXT_ERROR } from "@/lib/constants/validation";
import { queryKeys } from "@/lib/query-keys";
import { StrategyEmotionFields } from "./StrategyEmotionFields";
import { EMOTION_VALUES } from "./constants";
import { cn } from "@/lib/utils";
import { TradeFreeTextField } from "./TradeFreeTextField";
import { TradeHoldingSection } from "./TradeHoldingSection";

const schema = z.object({
  emotion: z.enum(EMOTION_VALUES).nullable(),
  sell_reason: z.string().max(VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX, TRADE_FREE_TEXT_ERROR),
});

type FormValues = z.infer<typeof schema>;

function BreakdownRow({ label, amount, prefix }: {
  label: string;
  amount: number;
  prefix?: "+" | "-";
}) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-[12px] tabular-nums text-foreground">
        {prefix ?? ""}{amount.toLocaleString("ko-KR")}원
      </span>
    </div>
  );
}

interface TradeMetaSellFormProps {
  tradeId: string;
  tradedAt: string;
  onDone: () => void;
}

export function TradeMetaSellForm({ tradeId, tradedAt, onDone }: TradeMetaSellFormProps) {
  const queryClient = useQueryClient();

  const { data: summary, isPending: summaryLoading } = useQuery({
    queryKey: queryKeys.tradeSummary(tradeId),
    queryFn: () => tradesApi.summary(tradeId),
  });

  const {
    control,
    handleSubmit,
    register,
    setError,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      emotion: null,
      sell_reason: "",
    },
  });

  const sellReason = useWatch({ control, name: "sell_reason" }) ?? "";

  async function onSubmit(values: FormValues) {
    try {
      await tradesApi.update(tradeId, {
        emotion: values.emotion,
        sell_reason: values.sell_reason.trim() || null,
        result: summary?.result ?? null,
        strategy_type: summary?.strategyEvaluation?.planned ?? null,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.trade(tradeId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
      ]);
      onDone();
    } catch (err) {
      setError("root", { message: err instanceof Error ? err.message : "저장에 실패했습니다." });
    }
  }

  const errorMessage = errors.root?.message ?? Object.values(errors)[0]?.message;
  const pnl = summary?.pnl;
  const result = summary?.result;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-6">

        {/* 거래 결과 (자동 계산) */}
        <div className="rounded-2xl bg-muted/60 p-4 space-y-3">
          <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wide">거래 결과 (자동 계산)</p>

          {summaryLoading ? (
            <p className="text-[13px] text-muted-foreground">계산 중...</p>
          ) : (
            <>
              {/* 거래 결과 + 손익 */}
              <div className="flex items-center justify-between">
                <span className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-bold border",
                  result === "SUCCESS" && "bg-[var(--rise)]/10 text-[var(--rise)] border-[var(--rise)]/30",
                  result === "FAIL" && "bg-[var(--fall)]/10 text-[var(--fall)] border-[var(--fall)]/30",
                  result === "BREAKEVEN" && "bg-muted text-foreground border-border",
                  !result && "bg-muted text-muted-foreground border-border",
                )}>
                  {result === "SUCCESS" ? "수익 ✅" : result === "FAIL" ? "손실 ❌" : result === "BREAKEVEN" ? "본전 ➖" : "–"}
                </span>
                {pnl != null && (
                  <span className={cn(
                    "text-[16px] font-bold tabular-nums",
                    pnl > 0 && "text-[var(--rise)]",
                    pnl < 0 && "text-[var(--fall)]",
                  )}>
                    {pnl >= 0 ? "+" : ""}{pnl.toLocaleString("ko-KR")}원
                  </span>
                )}
              </div>

              {/* 계산 과정 */}
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
                  {summary.breakdown.commission > 0 && (
                    <BreakdownRow label="수수료" amount={summary.breakdown.commission} prefix="-" />
                  )}
                  {summary.breakdown.tax > 0 && (
                    <BreakdownRow label="세금" amount={summary.breakdown.tax} prefix="-" />
                  )}
                  <div className="border-t border-border/60 pt-1.5 flex justify-between items-center">
                    <span className="text-[12px] font-semibold text-foreground">실현손익</span>
                    <span className={cn(
                      "text-[13px] font-bold tabular-nums",
                      pnl != null && pnl > 0 && "text-[var(--rise)]",
                      pnl != null && pnl < 0 && "text-[var(--fall)]",
                    )}>
                      {pnl != null ? `${pnl >= 0 ? "+" : ""}${pnl.toLocaleString("ko-KR")}원` : "–"}
                    </span>
                  </div>
                </div>
              )}
              {summary?.breakdown?.isManualInput && (
                <p className="text-[11px] text-muted-foreground">직접 입력한 손익 금액을 사용합니다.</p>
              )}
            </>
          )}
        </div>

        {/* 보유 정보 */}
        <TradeHoldingSection
          tradedAt={tradedAt}
          holdingDays={summary?.holdingDays ?? null}
          strategyEvaluation={summary?.strategyEvaluation ?? null}
        />

        <TradeFreeTextField
          id="sell_reason"
          label="매도 이유"
          valueLength={sellReason.length}
          {...register("sell_reason")}
          placeholder="왜 매도했나요?"
          rows={2}
        />

        <Controller
          control={control}
          name="emotion"
          render={({ field: emoField }) => (
            <StrategyEmotionFields
              strategy=""
              emotion={emoField.value ?? ""}
              onStrategyChange={() => {}}
              onEmotionChange={(v) => emoField.onChange(v || null)}
              hideStrategy
            />
          )}
        />

        {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
      </div>

      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4 flex gap-3"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <Button type="button" variant="outline" size="xl" className="flex-1" onClick={onDone}>
          건너뛰기
        </Button>
        <Button type="submit" size="xl" disabled={isSubmitting} className="flex-1">
          {isSubmitting ? "저장 중..." : "저장"}
        </Button>
      </div>
    </form>
  );
}
