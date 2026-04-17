"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/base/Tabs";
import type { Period } from "@/lib/analysis/period";

const PERIODS: { value: Period; label: string }[] = [
  { value: "1m", label: "1개월" },
  { value: "3m", label: "3개월" },
  { value: "6m", label: "6개월" },
  { value: "ytd", label: "올해" },
  { value: "all", label: "전체" },
];

interface PeriodFilterTabsProps {
  value: Period;
  onChange: (period: Period) => void;
}

export function PeriodFilterTabs({ value, onChange }: PeriodFilterTabsProps) {
  return (
    <Tabs value={value} onValueChange={(v) => onChange(v as Period)}>
      <TabsList className="grid grid-cols-5">
        {PERIODS.map((p) => (
          <TabsTrigger key={p.value} value={p.value} className="text-[12px]">
            {p.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
