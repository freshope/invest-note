"use client";

import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { tradesApi } from "@/lib/api-client";
import type { TradeResult } from "@/types/database";
import { StrategyEmotionFields } from "./StrategyEmotionFields";

const schema = z.object({
  result: z.enum(["SUCCESS", "FAIL", "BREAKEVEN"]).nullable(),
  strategy_type: z.enum(["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"]).nullable(),
  emotion: z.enum(["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]).nullable(),
  profit_loss_display: z.string(),
  sell_reason: z.string(),
  reflection_note: z.string(),
  improvement_note: z.string(),
});

type FormValues = z.infer<typeof schema>;

const RESULTS: { value: TradeResult; label: string; color: string }[] = [
  { value: "SUCCESS", label: "수익 ✅", color: "bg-[var(--rise)] text-white border-[var(--rise)]" },
  { value: "FAIL", label: "손실 ❌", color: "bg-[var(--fall)] text-white border-[var(--fall)]" },
  { value: "BREAKEVEN", label: "본전 ➖", color: "bg-muted text-foreground border-border" },
];

function formatNumber(raw: string): string {
  const cleaned = raw.replace(/[^0-9-]/g, "");
  if (!cleaned || cleaned === "-") return cleaned;
  const isNeg = cleaned.startsWith("-");
  const digits = cleaned.replace(/-/g, "");
  if (!digits) return isNeg ? "-" : "";
  return (isNeg ? "-" : "") + Number(digits).toLocaleString("ko-KR");
}

interface TradeMetaSellFormProps {
  tradeId: string;
  onDone: () => void;
}

export function TradeMetaSellForm({ tradeId, onDone }: TradeMetaSellFormProps) {
  const queryClient = useQueryClient();
  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    setError,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      result: null,
      strategy_type: null,
      emotion: null,
      profit_loss_display: "",
      sell_reason: "",
      reflection_note: "",
      improvement_note: "",
    },
  });

  const result = watch("result");

  async function onSubmit(values: FormValues) {
    try {
      const raw = values.profit_loss_display.replace(/,/g, "");
      await tradesApi.update(tradeId, {
        result: values.result,
        strategy_type: values.strategy_type,
        emotion: values.emotion,
        profit_loss: raw ? Number(raw) : null,
        sell_reason: values.sell_reason.trim() || null,
        reflection_note: values.reflection_note.trim() || null,
        improvement_note: values.improvement_note.trim() || null,
      });
      await queryClient.invalidateQueries({ queryKey: ["trade", tradeId] });
      onDone();
    } catch (err) {
      setError("root", { message: err instanceof Error ? err.message : "저장에 실패했습니다." });
    }
  }

  const errorMessage = errors.root?.message ?? Object.values(errors)[0]?.message;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-6">
        <div className="space-y-2">
          <Label>거래 결과</Label>
          <div className="grid grid-cols-3 gap-2">
            {RESULTS.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setValue("result", result === r.value ? null : r.value)}
                className={`rounded-xl border py-3 text-[13px] font-bold transition-colors ${
                  result === r.value ? r.color : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="profit_loss_input">
            손익 금액 (원){" "}
            <span className="text-[12px] font-normal text-muted-foreground">음수=손실</span>
          </Label>
          <Controller
            control={control}
            name="profit_loss_display"
            render={({ field }) => (
              <Input
                id="profit_loss_input"
                type="text"
                inputMode="numeric"
                placeholder="예: 150,000 또는 -50,000"
                value={field.value}
                onChange={(e) => field.onChange(formatNumber(e.target.value))}
              />
            )}
          />
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
          name="strategy_type"
          render={({ field: stratField }) => (
            <Controller
              control={control}
              name="emotion"
              render={({ field: emoField }) => (
                <StrategyEmotionFields
                  strategy={stratField.value ?? ""}
                  emotion={emoField.value ?? ""}
                  onStrategyChange={(v) => stratField.onChange(v || null)}
                  onEmotionChange={(v) => emoField.onChange(v || null)}
                />
              )}
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
