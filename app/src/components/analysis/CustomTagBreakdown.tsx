"use client";

import { TagBreakdownList } from "./TagBreakdownList";
import type { CustomTagStats } from "@/lib/analysis/aggregate";

interface CustomTagBreakdownProps {
  data: CustomTagStats[];
}

export function CustomTagBreakdown({ data }: CustomTagBreakdownProps) {
  return (
    <div className="space-y-3">
      <TagBreakdownList<CustomTagStats> data={data} getLabel={(d) => d.tag} />
    </div>
  );
}
