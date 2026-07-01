"use client";

import { useForm, Controller, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { Label } from "@/components/base/Label";
import { tradesApi } from "@/lib/api-client";
import { VALIDATION_LIMITS, TRADE_FREE_TEXT_ERROR } from "@/lib/constants/validation";
import { queryKeys } from "@/lib/query-keys";
import {
  STRATEGIES,
  EMOTIONS,
  STRATEGY_VALUES,
  EMOTION_VALUES,
  REASONING_TAG_VALUES,
} from "@/lib/constants/trading";
import { ToggleChipGrid } from "@/components/shared/ToggleChipGrid";
import { AnalysisTagsField } from "./AnalysisTagsField";
import { TradeFreeTextField } from "./TradeFreeTextField";
import { toastFirstFormError, toastSubmitError } from "@/lib/form-errors";
import type { StrategyType, EmotionType } from "@/types/database";

const schema = z.object({
  strategy_type: z.enum(STRATEGY_VALUES).nullable(),
  emotion: z.enum(EMOTION_VALUES).nullable(),
  reasoning_tags: z.array(z.enum(REASONING_TAG_VALUES)),
  custom_tags: z.array(z.string()),
  buy_reason: z.string().max(VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX, TRADE_FREE_TEXT_ERROR),
});

type FormValues = z.infer<typeof schema>;

interface TradeMetaBuyFormProps {
  tradeId: string;
  onDone: () => void;
}

export function TradeMetaBuyForm({ tradeId, onDone }: TradeMetaBuyFormProps) {
  const queryClient = useQueryClient();
  const {
    control,
    register,
    handleSubmit,
    setValue,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      strategy_type: null,
      emotion: null,
      reasoning_tags: [],
      custom_tags: [],
      buy_reason: "",
    },
  });

  const tags = useWatch({ control, name: "reasoning_tags" });
  const customTags = useWatch({ control, name: "custom_tags" });
  const buyReason = useWatch({ control, name: "buy_reason" }) ?? "";

  async function onSubmit(values: FormValues) {
    try {
      await tradesApi.update(tradeId, {
        strategy_type: values.strategy_type,
        emotion: values.emotion,
        reasoning_tags: values.reasoning_tags,
        custom_tags: values.custom_tags,
        buy_reason: values.buy_reason.trim() || null,
      });
      // BUY meta 변경 → BE가 매칭 SELL의 emotion/strategy 자동 산출. trades 리스트 + tradeSummary 모두 stale.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.trade(tradeId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.tradeSummary(tradeId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
      ]);
      onDone();
    } catch (err) {
      toastSubmitError(err);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit, toastFirstFormError)} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-6">
        <div className="space-y-6">
          <div className="space-y-2">
            <Label>전략</Label>
            <Controller
              control={control}
              name="strategy_type"
              render={({ field }) => (
                <ToggleChipGrid<StrategyType>
                  options={STRATEGIES}
                  value={field.value}
                  onChange={field.onChange}
                  emptyValue={null}
                  columns={4}
                />
              )}
            />
          </div>
          <div className="space-y-2">
            <Label>감정</Label>
            <Controller
              control={control}
              name="emotion"
              render={({ field }) => (
                <ToggleChipGrid<EmotionType>
                  options={EMOTIONS}
                  value={field.value}
                  onChange={field.onChange}
                  emptyValue={null}
                  columns={3}
                />
              )}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>
            분석 태그{" "}
            <span className="text-[12px] font-normal text-muted-foreground">(복수 선택)</span>
          </Label>
          <AnalysisTagsField
            reasoningTags={tags}
            customTags={customTags}
            onReasoningChange={(next) => setValue("reasoning_tags", next)}
            onCustomChange={(next) => setValue("custom_tags", next)}
          />
        </div>

        <TradeFreeTextField
          id="buy_reason"
          label="매수 메모"
          optional
          valueLength={buyReason.length}
          {...register("buy_reason")}
          placeholder="매수 메모를 간단히 적어주세요"
          rows={3}
        />
      </div>

      <FullScreenPanelFooter className="flex gap-3">
        <Button type="button" variant="outline" size="xl" className="flex-1" onClick={onDone}>
          건너뛰기
        </Button>
        <Button type="submit" size="xl" disabled={isSubmitting} className="flex-1">
          {isSubmitting ? "저장 중..." : "저장"}
        </Button>
      </FullScreenPanelFooter>
    </form>
  );
}
