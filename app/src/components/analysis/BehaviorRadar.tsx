"use client";

import { useMemo } from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import type { BehaviorProfile, ProfileInputRates } from "@/lib/analysis/profile";

const DIMENSIONS = [
  { key: "tempo" as const, label: "거래 템포", lowLabel: "스캘퍼", highLabel: "장기" },
  { key: "diversification" as const, label: "분산도*", lowLabel: "집중형", highLabel: "분산형" },
  { key: "emotionStability" as const, label: "감정 안정성", lowLabel: "충동형", highLabel: "차분형" },
  { key: "reasoningQuality" as const, label: "근거 품질", lowLabel: "감각형", highLabel: "분석형" },
  { key: "reviewHabit" as const, label: "복기 습관", lowLabel: "무복기", highLabel: "복기형" },
];

function ProfileBadge({
  dim,
  value,
  inputRate,
}: {
  dim: (typeof DIMENSIONS)[number];
  value: number;
  inputRate: number;
}) {
  const label = value < 35 ? dim.lowLabel : value > 65 ? dim.highLabel : "균형";
  const lowInput = inputRate < 50;
  return (
    <div className="flex flex-col items-center gap-0.5 min-w-0">
      <span className="text-[10px] text-muted-foreground text-center leading-tight">{dim.label}</span>
      <span className="text-[12px] font-semibold text-foreground">{label}</span>
      <span className="text-[10px] tabular-nums text-muted-foreground">{Math.round(value)}점</span>
      {lowInput && (
        <span className="text-[9px] text-amber-500">입력 {Math.round(inputRate)}%</span>
      )}
    </div>
  );
}

interface BehaviorRadarProps {
  profile: BehaviorProfile;
  inputRates: ProfileInputRates;
}

export function BehaviorRadar({ profile, inputRates }: BehaviorRadarProps) {
  const data = useMemo(
    () =>
      DIMENSIONS.map((d) => ({
        subject: d.label,
        value: profile[d.key],
        fullMark: 100,
      })),
    [profile],
  );

  const dimInputRates = useMemo<Record<string, number>>(
    () => ({
      tempo: inputRates.holdingDays,
      diversification: 100,
      emotionStability: inputRates.emotion,
      reasoningQuality: inputRates.reasoningTag,
      reviewHabit: inputRates.reflection,
    }),
    [inputRates],
  );

  return (
    <div className="space-y-4">
      <p className="text-[10px] text-muted-foreground">* 분산도는 현재 보유 포트폴리오 기준</p>

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
            />
          </RadarChart>
      </ResponsiveContainer>

      <div className="grid grid-cols-5 gap-1">
        {DIMENSIONS.map((d) => (
          <ProfileBadge
            key={d.key}
            dim={d}
            value={profile[d.key]}
            inputRate={dimInputRates[d.key]}
          />
        ))}
      </div>
    </div>
  );
}
