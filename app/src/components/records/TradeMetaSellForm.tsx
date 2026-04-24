"use client";

import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { StrategyEmotionFields } from "./StrategyEmotionFields";
import { EMOTION_VALUES } from "./constants";
import { cn } from "@/lib/utils";
import { STRATEGY_LABELS, ADHERENCE_CONFIG } from "@/lib/constants/trading";

const schema = z.object({
  emotion: z.enum(EMOTION_VALUES).nullable(),
  sell_reason: z.string(),
  reflection_note: z.string(),
  improvement_note: z.string(),
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
  onDone: () => void;
}

export function TradeMetaSellForm({ tradeId, onDone }: TradeMetaSellFormProps) {
  const queryClient = useQueryClient();

  const { data: summary, isPending: summaryLoading } = useQuery({
    queryKey: queryKeys.tradeSummary(tradeId),
    queryFn: () => tradesApi.summary(tradeId),
  });

  const {
    control,
    register,
    handleSubmit,
    setError,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      emotion: null,
      sell_reason: "",
      reflection_note: "",
      improvement_note: "",
    },
  });

  async function onSubmit(values: FormValues) {
    try {
      await tradesApi.update(tradeId, {
        emotion: values.emotion,
        sell_reason: values.sell_reason.trim() || null,
        reflection_note: values.reflection_note.trim() || null,
        improvement_note: values.improvement_note.trim() || null,
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
  const holdingDays = summary?.holdingDays;
  const stratEval = summary?.strategyEvaluation;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-6">

        {/* 자동 계산 요약 카드 */}
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

              {/* 보유 기간 + 전략 평가 */}
              {holdingDays != null && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[12px] text-muted-foreground">
                    보유 {holdingDays}일
                    {stratEval && ` · ${STRATEGY_LABELS[stratEval.actual] ?? stratEval.actual}`}
                  </span>
                  {stratEval && stratEval.adherence !== "UNKNOWN" && (
                    <span className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold border",
                      ADHERENCE_CONFIG[stratEval.adherence].className,
                    )}>
                      {stratEval.planned && `계획: ${STRATEGY_LABELS[stratEval.planned] ?? stratEval.planned} · `}
                      {ADHERENCE_CONFIG[stratEval.adherence].label}
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="sell_reason">매도 이유</Label>
          <Textarea
            id="sell_reason"
            {...register("sell_reason")}
            placeholder="왜 매도했나요?"
            rows={2}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="reflection_note">잘한 점 / 배운 점</Label>
          <Textarea
            id="reflection_note"
            {...register("reflection_note")}
            placeholder="이번 거래에서 잘한 점이나 배운 것을 기록해보세요"
            rows={3}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="improvement_note">개선할 점 / 다음에는</Label>
          <Textarea
            id="improvement_note"
            {...register("improvement_note")}
            placeholder="다음 거래에서 개선하고 싶은 점을 적어주세요"
            rows={3}
          />
        </div>

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
