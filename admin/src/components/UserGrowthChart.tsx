"use client";

import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { adminApi } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/base/Chart";

const chartConfig = {
  cumulative: { label: "누적 사용자", color: "var(--chart-1)" },
} satisfies ChartConfig;

// YYYY-MM-DD → M/D (축 라벨 간결화).
function fmtTick(date: string): string {
  const [, m, d] = date.split("-");
  return `${Number(m)}/${Number(d)}`;
}

export function UserGrowthChart() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "user-growth"],
    queryFn: () => adminApi.userGrowth(),
  });

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <p className="text-[13px] text-muted-foreground">누적 사용자수</p>

      {error ? (
        <div className="mt-3">
          <ApiErrorState error={error} />
        </div>
      ) : isLoading ? (
        <p className="mt-2 text-[14px] text-muted-foreground">불러오는 중…</p>
      ) : !data || data.length === 0 ? (
        <p className="mt-2 text-[14px] text-muted-foreground">데이터가 없습니다.</p>
      ) : (
        <ChartContainer config={chartConfig} className="mt-3 h-[280px] w-full">
          <LineChart data={data} margin={{ left: 4, right: 12, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={fmtTick}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              allowDecimals={false}
              width={36}
            />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Line
              dataKey="cumulative"
              type="monotone"
              stroke="var(--color-cumulative)"
              strokeWidth={2}
              // 점이 하나면 선이 안 보이므로 그 경우에만 dot 표시.
              dot={data.length === 1}
            />
          </LineChart>
        </ChartContainer>
      )}
    </div>
  );
}
