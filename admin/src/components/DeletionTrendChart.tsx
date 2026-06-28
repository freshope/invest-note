"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/base/Chart";
import type { DeletionTrendPoint } from "@/lib/api";

const chartConfig = {
  deletions: { label: "탈퇴 수", color: "var(--chart-2)" },
} satisfies ChartConfig;

// YYYY-MM-DD → M/D (축 라벨 간결화).
function fmtTick(date: string): string {
  const [, m, d] = date.split("-");
  return `${Number(m)}/${Number(d)}`;
}

// 데이터는 상위 페이지의 단일 deletion-stats 쿼리에서 prop 으로 받는다(중복 fetch 방지).
export function DeletionTrendChart({ data }: { data: DeletionTrendPoint[] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <p className="text-[13px] text-muted-foreground">탈퇴 추이</p>

      {data.length === 0 ? (
        <p className="mt-2 text-[14px] text-muted-foreground">데이터가 없습니다.</p>
      ) : (
        <ChartContainer config={chartConfig} className="mt-3 h-[280px] w-full">
          <BarChart data={data} margin={{ left: 4, right: 12, top: 8 }}>
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
            <Bar dataKey="deletions" fill="var(--color-deletions)" radius={2} />
          </BarChart>
        </ChartContainer>
      )}
    </div>
  );
}
