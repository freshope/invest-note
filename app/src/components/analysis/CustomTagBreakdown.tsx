"use client";

import { BreakdownList } from "./BreakdownList";
import type { CustomTagStats } from "@/lib/analysis/aggregate";

interface CustomTagBreakdownProps {
  data: CustomTagStats[];
}

export function CustomTagBreakdown({ data }: CustomTagBreakdownProps) {
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-muted-foreground">
        한 거래가 여러 태그에 포함되어 합계가 총 실현손익과 다를 수 있습니다.
      </p>

      <BreakdownList<CustomTagStats>
        data={data}
        emptyMessage="매칭된 태그 데이터가 없습니다"
        getKey={(d) => d.tag}
        isUntagged={() => false}
        getLabel={(d) => d.tag}
        getStats={(d) => ({
          count: d.count,
          sumPnL: d.sumPnL,
          winRate: d.winRate,
          hasData: d.count > 0,
        })}
      />
    </div>
  );
}
