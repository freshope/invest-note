"use client";

import { useActionState, useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { Button } from "@/components/base/Button";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/base/ToggleGroup";
import { updateTradeMetadata, type MetaActionState } from "@/app/(app)/records/actions";
import type { StrategyType, EmotionType, ReasoningTag } from "@/types/database";
import { STRATEGIES, EMOTIONS, REASONING_TAGS } from "./constants";

interface TradeMetaBuyFormProps {
  tradeId: string;
  onDone: () => void;
}

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="xl" disabled={pending} className="w-full">
      {pending ? "저장 중..." : "저장"}
    </Button>
  );
}

export function TradeMetaBuyForm({ tradeId, onDone }: TradeMetaBuyFormProps) {
  const [state, formAction] = useActionState<MetaActionState, FormData>(updateTradeMetadata, undefined);

  const [strategy, setStrategy] = useState<StrategyType | "">("");
  const [emotion, setEmotion] = useState<EmotionType | "">("");
  const [tags, setTags] = useState<ReasoningTag[]>([]);

  useEffect(() => {
    if (state && "success" in state && state.success) {
      onDone();
    }
  }, [state, onDone]);

  function toggleTag(tag: ReasoningTag) {
    setTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }

  return (
    <form action={formAction} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-6">
        <input type="hidden" name="id" value={tradeId} />
        <input type="hidden" name="strategy_type" value={strategy} />
        <input type="hidden" name="emotion" value={emotion} />
        <input type="hidden" name="reasoning_tags" value={tags.join(",")} />

        {/* 전략 */}
        <div className="space-y-2">
          <Label>전략</Label>
          <div className="grid grid-cols-4 gap-2">
            {STRATEGIES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => setStrategy(strategy === s.value ? "" : s.value)}
                className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                  strategy === s.value
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* 감정 */}
        <div className="space-y-2">
          <Label>감정</Label>
          <div className="grid grid-cols-3 gap-2">
            {EMOTIONS.map((e) => (
              <button
                key={e.value}
                type="button"
                onClick={() => setEmotion(emotion === e.value ? "" : e.value)}
                className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                  emotion === e.value
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {e.label}
              </button>
            ))}
          </div>
        </div>

        {/* 분석 태그 */}
        <div className="space-y-2">
          <Label>분석 태그 <span className="text-[12px] font-normal text-muted-foreground">(복수 선택)</span></Label>
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

        {/* 매매 이유 */}
        <div className="space-y-1.5">
          <Label htmlFor="buy_reason">매매 이유 <span className="text-[12px] font-normal text-muted-foreground">(선택)</span></Label>
          <Textarea
            id="buy_reason"
            name="buy_reason"
            placeholder="매수 이유를 간단히 적어주세요"
            rows={3}
          />
        </div>

        {state && "error" in state && (
          <p className="text-sm text-destructive">{state.error}</p>
        )}
      </div>

      {/* 하단 버튼 */}
      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4 flex gap-3"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <Button type="button" variant="outline" size="xl" className="flex-1" onClick={onDone}>
          건너뛰기
        </Button>
        <div className="flex-1">
          <SubmitButton />
        </div>
      </div>
    </form>
  );
}
