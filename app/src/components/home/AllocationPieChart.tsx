"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

export interface DonutEntry {
  name: string;
  value: number;
  color?: string;
}

interface AllocationPieChartProps {
  data: DonutEntry[];
  fallbackColors: string[];
}

export default function AllocationPieChart({ data, fallbackColors }: AllocationPieChartProps) {
  return (
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
            <Cell key={entry.name} fill={entry.color ?? fallbackColors[i % fallbackColors.length]} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}
