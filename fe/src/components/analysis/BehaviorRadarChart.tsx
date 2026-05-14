"use client";

import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";

export interface RadarDatum {
  subject: string;
  value: number;
  fullMark: number;
}

interface BehaviorRadarChartProps {
  data: RadarDatum[];
}

export default function BehaviorRadarChart({ data }: BehaviorRadarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={208}>
      <RadarChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
        <PolarGrid gridType="polygon" stroke="var(--border)" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
        />
        <Radar
          dataKey="value"
          stroke="var(--chart-1)"
          fill="var(--chart-1)"
          fillOpacity={0.25}
          strokeWidth={2}
          activeDot={false}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
