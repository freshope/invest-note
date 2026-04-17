"use client";

import { cn } from "@/lib/utils";
import { SEVERITY_STYLES } from "./severity-styles";
import type { Suggestion } from "@/lib/analysis/rules";

interface InsightHighlightsProps {
  insights: Suggestion[];
}

export function InsightHighlights({ insights }: InsightHighlightsProps) {
  if (insights.length === 0) return null;

  return (
    <div className="space-y-2">
      {insights.map((insight) => {
        const style = SEVERITY_STYLES[insight.severity];
        const Icon = style.icon;
        return (
          <div
            key={insight.id}
            className={cn("rounded-2xl border p-3.5 flex gap-3", style.bg, style.border)}
          >
            <Icon className={cn("w-4 h-4 shrink-0 mt-0.5", style.iconClass)} />
            <div className="space-y-0.5">
              <p className="text-[13px] font-semibold text-foreground">{insight.title}</p>
              <p className="text-[12px] text-muted-foreground leading-snug">{insight.body}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
