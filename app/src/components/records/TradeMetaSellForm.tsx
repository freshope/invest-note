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
import { TradeFreeTextField } from "./TradeFreeTextField";

const schema = z.object({
  emotion: z.enum(EMOTION_VALUES).nullable(),
  sell_reason: z.string().max(VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX, TRADE_FREE_TEXT_ERROR),
});

type FormValues = z.infer<typeof schema>;

interface TradeMetaSellFormProps {
  tradeId: string;
  onDone: () => void;
}

export function TradeMetaSellForm({ tradeId, onDone }: TradeMetaSellFormProps) {
  const queryClient = useQueryClient();

  const { data: summary } = useQuery({
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

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-6">

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
