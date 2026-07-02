"use client";

import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { REASONING_TAG_LABELS, UNTAGGED_KEY } from "@/lib/constants/trading";
import { SEMANTIC_COLORS } from "@/lib/constants/semantic-colors";
import { TagBreakdownList } from "./TagBreakdownList";
import type { TagStats, AnalysisSummary } from "@/lib/analysis/aggregate";

interface ReasoningBreakdownProps {
  data: TagStats[];
  summary: Pick<AnalysisSummary, "feelingRate" | "missingTagRate">;
}

export function ReasoningBreakdown({ data, summary }: ReasoningBreakdownProps) {
  const showFeelingWarn = summary.feelingRate >= 40;
  const showMissingWarn = summary.missingTagRate >= 30;

  return (
    <div className="space-y-3">
      <TagBreakdownList<TagStats>
        data={data}
        getLabel={(d) => REASONING_TAG_LABELS[d.tag] ?? d.tag}
        isUntagged={(d) => d.tag === UNTAGGED_KEY}
      />

      {(showFeelingWarn || showMissingWarn) && (
        <div className={cn("rounded-xl border p-3 flex gap-2 items-start", SEMANTIC_COLORS.warning.bgSoft, SEMANTIC_COLORS.warning.borderSoft)}>
          <AlertTriangle className={cn("w-3.5 h-3.5 shrink-0 mt-0.5", SEMANTIC_COLORS.warning.text)} />
          <p className={cn("text-[12px] leading-snug", SEMANTIC_COLORS.warning.text)}>
            {showFeelingWarn && `'감/직감' 진입 ${Math.round(summary.feelingRate)}% `}
            {showMissingWarn && `근거 태그 누락 ${Math.round(summary.missingTagRate)}%`}
            {(showFeelingWarn || showMissingWarn) && " — 분석 근거를 추가해보세요"}
          </p>
        </div>
      )}
    </div>
  );
}
