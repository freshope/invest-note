"use client";

import { useMemo } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/base/Tabs";
import { fmtCompact } from "@/lib/format";
import type { Position, AccountSnapshot } from "@/lib/portfolio";

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "#A78BFA",
  "#34D399",
  "#FB923C",
];

interface DonutEntry {
  name: string;
  value: number;
}

interface AllocationDonutProps {
  data: DonutEntry[];
  total: number;
  label: string;
}

function AllocationDonut({ data, total, label }: AllocationDonutProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-[13px] text-muted-foreground">
        데이터 없음
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative h-44">
        <ResponsiveContainer width="100%" height={176}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius="58%"
              outerRadius="85%"
              paddingAngle={2}
              dataKey="value"
              strokeWidth={0}
            >
              {data.map((entry, i) => (
                <Cell key={entry.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => [`${Number(value).toLocaleString("ko-KR")}원`, ""]}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* 중앙 텍스트 */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <p className="text-[11px] text-muted-foreground">{label}</p>
          <p className="text-[17px] font-bold tabular-nums text-foreground">{fmtCompact(total)}원</p>
        </div>
      </div>

      {/* 범례 */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {data.map((entry, i) => {
          const pct = total > 0 ? Math.round((entry.value / total) * 100) : 0;
          return (
            <div key={entry.name} className="flex items-center gap-1.5 min-w-0">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
              />
              <span className="text-[12px] text-foreground truncate flex-1">{entry.name}</span>
              <span className="text-[12px] tabular-nums text-muted-foreground shrink-0">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface AllocationTabsProps {
  positions: Position[];
  snapshots: AccountSnapshot[];
}

export function AllocationTabs({ positions, snapshots }: AllocationTabsProps) {
  const posData = useMemo<DonutEntry[]>(() => {
    const withEval = positions.filter((p) => (p.evaluation ?? 0) > 0);
    if (withEval.length === 0) return [];
    const sorted = [...withEval].sort((a, b) => (b.evaluation ?? 0) - (a.evaluation ?? 0));
    const top = sorted.slice(0, 7);
    const rest = sorted.slice(7);
    const out: DonutEntry[] = top.map((p) => ({ name: p.assetName, value: p.evaluation ?? 0 }));
    if (rest.length > 0) {
      out.push({ name: "기타", value: rest.reduce((s, p) => s + (p.evaluation ?? 0), 0) });
    }
    return out;
  }, [positions]);

  const posTotal = useMemo(() => posData.reduce((s, d) => s + d.value, 0), [posData]);

  const snapData = useMemo<DonutEntry[]>(
    () =>
      snapshots
        .filter((s) => s.totalValue > 0)
        .map((s) => ({ name: s.account.name, value: s.totalValue })),
    [snapshots],
  );
  const snapTotal = useMemo(() => snapData.reduce((s, d) => s + d.value, 0), [snapData]);

  return (
    <div className="px-5">
      <div className="rounded-2xl bg-muted/60 p-4">
        <Tabs defaultValue="stock">
          <TabsList className="mb-4">
            <TabsTrigger value="stock">종목별</TabsTrigger>
            <TabsTrigger value="account">계좌별</TabsTrigger>
          </TabsList>
          <TabsContent value="stock">
            <AllocationDonut data={posData} total={posTotal} label="주식 평가" />
          </TabsContent>
          <TabsContent value="account">
            <AllocationDonut data={snapData} total={snapTotal} label="계좌 총액" />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
