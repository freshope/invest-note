"use client";

import dynamic from "next/dynamic";
import type { AssetHistoryPoint } from "@/lib/api-client";

// 스와이프 터치 state 를 가진 인터랙티브 차트 → ssr:false (AllocationTabs 패턴).
const AssetHistoryChartInner = dynamic(() => import("./AssetHistoryChartInner"), {
  ssr: false,
  loading: () => <div style={{ height: 170 }} aria-hidden />,
});

export function AssetHistoryChart({
  series,
  investedAmount,
  onFocusChange,
}: {
  series: AssetHistoryPoint[];
  /** 매수 원금 가이드 라인 값 — null이면 기존 단색 차트 */
  investedAmount?: number | null;
  onFocusChange?: (point: AssetHistoryPoint) => void;
}) {
  if (series.length === 0) {
    return (
      <div className="flex h-[170px] items-center justify-center text-[13px] text-muted-foreground">
        표시할 데이터가 없어요
      </div>
    );
  }
  return (
    <AssetHistoryChartInner
      series={series}
      investedAmount={investedAmount}
      onFocusChange={onFocusChange}
    />
  );
}
