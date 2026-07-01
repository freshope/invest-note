"use client";

import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { tradesApi } from "@/lib/api-client";
import { VALIDATION_LIMITS, TRADE_FREE_TEXT_ERROR } from "@/lib/constants/validation";
import { queryKeys } from "@/lib/query-keys";
import { TradeFreeTextField } from "./TradeFreeTextField";
import { AutoBuyReasonField, AutoEmotionField, AutoReasoningTagsField } from "./AutoMetaField";
import { toastFirstFormError, toastSubmitError } from "@/lib/form-errors";

const schema = z.object({
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

  // 자동 산출된 emotion 표시용 — 직전 BUY로부터 백엔드가 자동 채움
  const { data: trade } = useQuery({
    queryKey: queryKeys.trade(tradeId),
    queryFn: () => tradesApi.get(tradeId),
  });

  const {
    control,
    handleSubmit,
    register,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { sell_reason: "" },
  });

  const sellReason = useWatch({ control, name: "sell_reason" }) ?? "";

  async function onSubmit(values: FormValues) {
    try {
      await tradesApi.update(tradeId, {
        sell_reason: values.sell_reason.trim() || null,
        // SELL의 result는 백엔드가 PnL 부호로 자동 산출 — 패치 미포함.
        strategy_type: summary?.strategyEvaluation?.planned ?? null,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.trade(tradeId) }),
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

        <TradeFreeTextField
          id="sell_reason"
          label="매도 이유"
          valueLength={sellReason.length}
          {...register("sell_reason")}
          placeholder="왜 매도했나요?"
          rows={2}
        />

        <AutoEmotionField emotion={trade?.emotion ?? null} />

        <AutoReasoningTagsField tags={trade?.reasoning_tags ?? null} />

        <AutoBuyReasonField reason={summary?.buyReason ?? null} />
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
