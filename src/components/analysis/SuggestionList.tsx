"use client";

import { AlertTriangle, Info, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Suggestion } from "@/lib/analysis/rules";

const SEVERITY_STYLES = {
  info: {
    bg: "bg-blue-50 dark:bg-blue-950/30",
    border: "border-blue-200 dark:border-blue-800",
    icon: Info,
    iconClass: "text-blue-500",
    metricClass: "text-blue-600 dark:text-blue-400",
  },
  warn: {
    bg: "bg-amber-50 dark:bg-amber-950/30",
    border: "border-amber-200 dark:border-amber-800",
    icon: AlertTriangle,
    iconClass: "text-amber-500",
    metricClass: "text-amber-600 dark:text-amber-400",
  },
  critical: {
    bg: "bg-red-50 dark:bg-red-950/30",
    border: "border-red-200 dark:border-red-800",
    icon: AlertCircle,
    iconClass: "text-red-500",
    metricClass: "text-red-600 dark:text-red-400",
  },
};

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
