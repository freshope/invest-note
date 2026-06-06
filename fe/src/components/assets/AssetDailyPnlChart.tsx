"use client";

import dynamic from "next/dynamic";
import type { AssetHistoryPoint } from "@/lib/api-client";

// 스와이프 터치 state 를 가진 인터랙티브 차트 → ssr:false (AssetHistoryChart 패턴).
const AssetDailyPnlChartInner = dynamic(() => import("./AssetDailyPnlChartInner"), {
  ssr: false,
  loading: () => <div style={{ height: 170 }} aria-hidden />,
});

export function AssetDailyPnlChart({
  series,
  onFocusChange,
}: {
  /** 일별 손익 시계열 — value = 전일대비('일별 내역' 표와 동일 값) */
  series: AssetHistoryPoint[];
  onFocusChange?: (point: AssetHistoryPoint) => void;
}) {
  if (series.length === 0) {
    return (
      <div className="flex h-[170px] items-center justify-center text-[13px] text-muted-foreground">
        표시할 데이터가 없어요
      </div>
    );
  }
  return <AssetDailyPnlChartInner series={series} onFocusChange={onFocusChange} />;
}
