"use client";

import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { tradesApi } from "@/lib/api-client";
import { REASONING_TAGS } from "./constants";
import { StrategyEmotionFields } from "./StrategyEmotionFields";

const schema = z.object({
  strategy_type: z.enum(["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"]).nullable(),
  emotion: z.enum(["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]).nullable(),
  reasoning_tags: z.array(z.enum(["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"])),
  buy_reason: z.string(),
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
    watch,
    setError,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      strategy_type: null,
      emotion: null,
      reasoning_tags: [],
      buy_reason: "",
    },
  });

  const tags = watch("reasoning_tags");

  function toggleTag(tag: FormValues["reasoning_tags"][number]) {
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    setValue("reasoning_tags", next);
  }

  async function onSubmit(values: FormValues) {
    try {
      await tradesApi.update(tradeId, {
        strategy_type: values.strategy_type,
        emotion: values.emotion,
        reasoning_tags: values.reasoning_tags,
        buy_reason: values.buy_reason.trim() || null,
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

        <div className="space-y-2">
          <Label>
            분석 태그{" "}
            <span className="text-[12px] font-normal text-muted-foreground">(복수 선택)</span>
          </Label>
          <div className="grid grid-cols-2 gap-2">
            {REASONING_TAGS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => toggleTag(t.value)}
                className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                  tags.includes(t.value)
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="buy_reason">
            매수 근거{" "}
            <span className="text-[12px] font-normal text-muted-foreground">(선택)</span>
          </Label>
          <Textarea
            id="buy_reason"
            {...register("buy_reason")}
            placeholder="매수한 근거를 간단히 적어주세요"
            rows={3}
          />
        </div>

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
