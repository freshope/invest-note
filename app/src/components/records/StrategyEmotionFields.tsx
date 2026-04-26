"use client";

import { Label } from "@/components/base/Label";
import type { StrategyType, EmotionType } from "@/types/database";
import { STRATEGIES, EMOTIONS } from "./constants";

interface StrategyEmotionFieldsProps {
  strategy: StrategyType | "";
  emotion: EmotionType | "";
  onStrategyChange: (value: StrategyType | "") => void;
  onEmotionChange: (value: EmotionType | "") => void;
  hideStrategy?: boolean;
  hideEmotion?: boolean;
}

export function StrategyEmotionFields({
  strategy,
  emotion,
  onStrategyChange,
  onEmotionChange,
  hideStrategy = false,
  hideEmotion = false,
}: StrategyEmotionFieldsProps) {
  return (
    <>
      {!hideStrategy && (
        <div className="space-y-2">
          <Label>전략</Label>
          <div className="grid grid-cols-4 gap-2">
            {STRATEGIES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => onStrategyChange(strategy === s.value ? "" : s.value)}
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
      )}

      {!hideEmotion && (
        <div className="space-y-2">
          <Label>감정</Label>
          <div className="grid grid-cols-3 gap-2">
            {EMOTIONS.map((e) => (
              <button
                key={e.value}
                type="button"
                onClick={() => onEmotionChange(emotion === e.value ? "" : e.value)}
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
      )}
    </>
  );
}
