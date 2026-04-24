"use client";

import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from "@/components/base/Tabs";
import type { Period } from "@/lib/constants/analysis";
import { PERIODS_FULL, PERIODS_COMPACT } from "@/lib/constants/analysis";

interface PeriodFilterTabsProps {
  value: Period;
  onChange: (period: Period) => void;
  compact?: boolean;
}

export function PeriodFilterTabs({ value, onChange, compact = false }: PeriodFilterTabsProps) {
  const items = compact ? PERIODS_COMPACT : PERIODS_FULL;
  return (
    <Tabs value={value} onValueChange={(v) => onChange(v as Period)}>
      <TabsList className={cn(compact ? "inline-flex h-8 p-0.5 w-auto" : "grid grid-cols-5")}>
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
