"use client";

import { Label } from "@/components/base/Label";
import { ToggleChipGrid } from "@/components/shared/ToggleChipGrid";
import type { StrategyType, EmotionType } from "@/types/database";
import { STRATEGIES, EMOTIONS } from "@/lib/constants/trading";

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
          <ToggleChipGrid<StrategyType, "">
            options={STRATEGIES}
            value={strategy}
            onChange={onStrategyChange}
            emptyValue=""
            columns={4}
          />
        </div>
      )}

      {!hideEmotion && (
        <div className="space-y-2">
          <Label>감정</Label>
          <ToggleChipGrid<EmotionType, "">
            options={EMOTIONS}
            value={emotion}
            onChange={onEmotionChange}
            emptyValue=""
            columns={3}
          />
        </div>
      )}
    </>
  );
}
