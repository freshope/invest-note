"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import type { BehaviorProfile, ProfileInputRates } from "@/lib/analysis/profile";

const BehaviorRadarChart = dynamic(() => import("./BehaviorRadarChart"), {
  ssr: false,
  loading: () => <div style={{ height: 208 }} aria-hidden />,
});

const DIMENSIONS = [
  { key: "tempo" as const, label: "거래 템포", lowLabel: "스캘퍼", highLabel: "장기" },
  { key: "emotionStability" as const, label: "감정 안정도", lowLabel: "불안정", highLabel: "안정" },
  { key: "reasoningQuality" as const, label: "근거 체계성", lowLabel: "감각형", highLabel: "분석형" },
  { key: "reviewHabit" as const, label: "복기 습관", lowLabel: "무복기", highLabel: "복기형" },
  { key: "strategyConsistency" as const, label: "전략 일관성", lowLabel: "이탈형", highLabel: "준수형" },
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
      emotionStability: inputRates.emotion,
      reasoningQuality: inputRates.reasoningTag,
      reviewHabit: inputRates.reflection,
      strategyConsistency: inputRates.strategy,
    }),
    [inputRates],
  );

  return (
    <div className="space-y-4">
      <div className="[&_*:focus]:outline-none">
        <BehaviorRadarChart data={data} />
      </div>

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
