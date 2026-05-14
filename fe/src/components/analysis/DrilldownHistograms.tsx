"use client";

interface Bucket {
  bucket: string;
  count: number;
}

function Histogram({ data, emptyText }: { data: Bucket[]; emptyText: string }) {
  if (data.length === 0) {
    return <p className="text-[12px] text-muted-foreground text-center py-3">{emptyText}</p>;
  }

  const max = Math.max(...data.map((d) => d.count));

  return (
    <div className="space-y-1.5">
      {data.map((item) => {
        const pct = max > 0 ? (item.count / max) * 100 : 0;
        return (
          <div key={item.bucket} className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground w-20 shrink-0 text-right">
              {item.bucket}
            </span>
            <div className="flex-1 h-4 rounded bg-muted overflow-hidden">
              <div
                className="h-full rounded bg-[var(--chart-2)]"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-[11px] tabular-nums text-muted-foreground w-6 text-right">
              {item.count}
            </span>
          </div>
        );
      })}
    </div>
  );
}

interface DrilldownHistogramsProps {
  holdingPeriodDist: Bucket[];
  positionSizeDist: Bucket[];
}

export function DrilldownHistograms({
  holdingPeriodDist,
  positionSizeDist,
}: DrilldownHistogramsProps) {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <p className="text-[12px] font-semibold text-muted-foreground">보유 기간 분포</p>
        <Histogram data={holdingPeriodDist} emptyText="매도 기록이 없습니다" />
      </div>
      <div className="space-y-2">
        <p className="text-[12px] font-semibold text-muted-foreground">매수 금액 분포</p>
        <Histogram data={positionSizeDist} emptyText="매수 기록이 없습니다" />
      </div>
    </div>
  );
}
