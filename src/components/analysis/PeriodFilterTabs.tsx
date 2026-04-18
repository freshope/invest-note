"use client";

import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from "@/components/base/Tabs";
import type { Period } from "@/lib/analysis/period";

const PERIODS_FULL: { value: Period; label: string }[] = [
  { value: "1m", label: "1개월" },
  { value: "3m", label: "3개월" },
  { value: "6m", label: "6개월" },
  { value: "ytd", label: "올해" },
  { value: "all", label: "전체" },
];

const PERIODS_COMPACT: { value: Period; label: string }[] = [
  { value: "1m", label: "1M" },
  { value: "3m", label: "3M" },
  { value: "6m", label: "6M" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "전체" },
];

interface PeriodFilterTabsProps {
  value: Period;
  onChange: (period: Period) => void;
  compact?: boolean;
}

export function PeriodFilterTabs({ value, onChange, compact = false }: PeriodFilterTabsProps) {
  const items = compact ? PERIODS_COMPACT : PERIODS_FULL;
  return (
    <Tabs value={value} onValueChange={(v) => onChange(v as Period)}>
      <TabsList className={cn(compact ? "inline-flex h-8 p-0.5" : "grid grid-cols-5")}>
        {items.map((p) => (
          <TabsTrigger
            key={p.value}
            value={p.value}
            className={cn(compact ? "h-7 px-2 text-[11px]" : "text-[12px]")}
          >
            {p.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
