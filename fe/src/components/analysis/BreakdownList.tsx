"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { PnLLine } from "./PnLLine";
import { WinRateBar } from "./WinRateBar";

export interface BreakdownStats {
  count: number;
  sumPnL: number;
  winRate: number;
  hasData: boolean;
}

interface BreakdownListProps<T> {
  data: T[];
  emptyMessage: string;
  getKey: (item: T) => string;
  isUntagged: (item: T) => boolean;
  getLabel: (item: T) => string;
  getStats: (item: T) => BreakdownStats;
  renderMeta?: (item: T) => ReactNode;
  emptyRateLabel?: string;
}

export function BreakdownList<T>({
  data,
  emptyMessage,
  getKey,
  isUntagged,
  getLabel,
  getStats,
  renderMeta,
  emptyRateLabel,
}: BreakdownListProps<T>) {
  if (data.length === 0) {
    return (
      <div className="text-[13px] text-muted-foreground text-center py-6">
        {emptyMessage}
      </div>
    );
  }

  const others = data.filter((d) => !isUntagged(d));
  const untagged = data.filter((d) => isUntagged(d));
  const sortedData = [...others, ...untagged];

  return (
    <div className="space-y-3">
      {sortedData.map((item) => {
        const isMuted = isUntagged(item);
        const stats = getStats(item);
        const meta = renderMeta?.(item);
        const labelSpan = (
          <span
            className={cn(
              "text-[13px] font-medium",
              isMuted ? "text-muted-foreground" : "text-foreground",
            )}
          >
            {getLabel(item)}
          </span>
        );
        return (
          <div key={getKey(item)} className="space-y-1.5">
            <div className="flex items-center justify-between">
              {meta ? (
                <div>
                  {labelSpan}
                  {meta}
                </div>
              ) : (
                labelSpan
              )}
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {stats.count}건
                <PnLLine value={stats.sumPnL} muted={isMuted} />
              </span>
            </div>
            <WinRateBar
              rate={stats.winRate}
              hasData={stats.hasData}
              emptyLabel={emptyRateLabel}
              muted={isMuted}
            />
          </div>
        );
      })}
    </div>
  );
}
