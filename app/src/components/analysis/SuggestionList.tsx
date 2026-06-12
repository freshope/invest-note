"use client";

import { cn } from "@/lib/utils";
import type { Suggestion } from "@/lib/analysis/rules";
import { SEVERITY_STYLES } from "./severity-styles";

interface SuggestionListProps {
  suggestions: Suggestion[];
}

export function SuggestionList({ suggestions }: SuggestionListProps) {
  if (suggestions.length === 0) {
    return (
      <p className="text-[13px] text-muted-foreground text-center py-4">
        아직 특이 패턴이 감지되지 않았어요
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {suggestions.map((s) => {
        const style = SEVERITY_STYLES[s.severity];
        const Icon = style.icon;
        return (
          <div
            key={s.id}
            className={cn("rounded-xl border p-3.5 flex gap-3", style.bg, style.border)}
          >
            <Icon className={cn("w-4 h-4 shrink-0 mt-0.5", style.iconClass)} />
            <div className="space-y-0.5 flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p className="text-[13px] font-semibold text-foreground">{s.title}</p>
                {s.metric && (
                  <span className={cn("text-[12px] font-bold tabular-nums shrink-0", style.metricClass)}>
                    {s.metric.value}
                  </span>
                )}
              </div>
              <p className="text-[12px] text-muted-foreground leading-snug">{s.body}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
