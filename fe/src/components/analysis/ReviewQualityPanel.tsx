"use client";

import { cn } from "@/lib/utils";
import type { ProfileInputRates } from "@/lib/analysis/profile";
import { ProgressTrack } from "@/components/shared/ProgressTrack";
import { pickRateColor } from "@/lib/analysis/rate-color";

const QUALITY_THRESHOLDS = { win: 70, loss: 40 };

function QualityBar({
  label,
  rate,
  description,
}: {
  label: string;
  rate: number;
  description: string;
}) {
  const pct = Math.round(rate);
  const { bg, text } = pickRateColor(pct, QUALITY_THRESHOLDS);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[13px] font-medium text-foreground">{label}</span>
          <p className="text-[11px] text-muted-foreground">{description}</p>
        </div>
        <span className={cn("text-[15px] font-bold tabular-nums", text)}>{pct}%</span>
      </div>
      <ProgressTrack pct={pct} colorClass={bg} />
    </div>
  );
}

interface ReviewQualityPanelProps {
  inputRates: ProfileInputRates;
  reflectionRate: number;
  resultInputRate: number;
}

export function ReviewQualityPanel({
  inputRates,
  reflectionRate,
  resultInputRate,
}: ReviewQualityPanelProps) {
  return (
    <div className="space-y-3">
      <QualityBar
        label="매도 이유 작성"
        rate={reflectionRate}
        description="매도 후 이유 작성률"
      />
      <QualityBar
        label="거래 결과 입력"
        rate={resultInputRate}
        description="승률 분석의 정확도 기반"
      />
      <QualityBar
        label="감정 기록"
        rate={inputRates.emotion}
        description="전체 거래 중 감정 입력률"
      />
      <QualityBar
        label="매수 근거 태그"
        rate={inputRates.reasoningTag}
        description="BUY 거래 중 태그 입력률"
      />
    </div>
  );
}
