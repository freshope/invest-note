"use client";

import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { calcPercent, formatPnL, signColor } from "@/lib/format";
import { ADHERENCE_CONFIG } from "@/lib/constants/trading";
import { SEMANTIC_COLORS } from "@/lib/constants/semantic-colors";
import type { StrategyAdherenceStats } from "@/lib/analysis/aggregate";

interface StrategyAdherencePanelProps {
  rate: number;
  data: StrategyAdherenceStats[];
}

// canonical PnLLine과 분리: 블록(`<p>`) + 11px 사이즈 — Adherence row 레이아웃 전용.
function AdherencePnL({ value }: { value: number }) {
  if (value === 0) return null;
  return (
    <p className={cn("text-[11px] tabular-nums", signColor(value, "none"))}>
      {formatPnL(value)}
    </p>
  );
}

function AdherenceSide({
  type,
  stats,
  align,
}: {
  type: "FOLLOWED" | "DEVIATED";
  stats: StrategyAdherenceStats | undefined;
  align: "left" | "right";
}) {
  const config = ADHERENCE_CONFIG[type];
  const count = stats?.count ?? 0;
  return (
    <div className={cn("space-y-0.5", align === "right" && "text-right")}>
      <p className={cn("font-semibold", config.textClassName)}>{config.label}</p>
      <p className="text-[11px] text-muted-foreground tabular-nums">
        {count}건
        {stats && stats.resultCount > 0 && (
          <span className="ml-1">· 승률 {Math.round(stats.winRate)}%</span>
        )}
      </p>
      <AdherencePnL value={stats?.sumPnL ?? 0} />
    </div>
  );
}

export function StrategyAdherencePanel({ rate, data }: StrategyAdherencePanelProps) {
  const followed = data.find((d) => d.type === "FOLLOWED");
  const deviated = data.find((d) => d.type === "DEVIATED");
  const unknown = data.find((d) => d.type === "UNKNOWN");

  const followedCount = followed?.count ?? 0;
  const deviatedCount = deviated?.count ?? 0;
  const unknownCount = unknown?.count ?? 0;
  const unknownPnL = unknown?.sumPnL ?? 0;
  const judged = followedCount + deviatedCount;
  const followedPct = calcPercent(followedCount, judged);
  const deviatedPct = judged > 0 ? 100 - followedPct : 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[12px] text-muted-foreground">전략 준수율</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">전략과 실제 보유일 기준</p>
        </div>
        <div className="text-right">
          <p className="text-[20px] font-bold tabular-nums text-foreground">
            {judged > 0 ? `${Math.round(rate)}%` : "-"}
          </p>
          <p className="text-[11px] text-muted-foreground">{judged}건 판정</p>
        </div>
      </div>

      {judged === 0 ? (
        <div className="text-[13px] text-muted-foreground text-center py-4">
          {unknownCount > 0
            ? `전략 준수 판정이 가능한 거래가 없습니다 (미입력 ${unknownCount}건)`
            : "전략 준수 데이터가 없습니다"}
        </div>
      ) : (
        <div className="space-y-1.5">
          <div className="flex items-start justify-between gap-2 text-[12px]">
            <AdherenceSide type="FOLLOWED" stats={followed} align="left" />
            <AdherenceSide type="DEVIATED" stats={deviated} align="right" />
          </div>

          <div className="flex h-2 rounded-full bg-muted overflow-hidden">
            {followedPct > 0 && (
              <div
                className={ADHERENCE_CONFIG.FOLLOWED.barClassName}
                style={{ width: `${followedPct}%` }}
              />
            )}
            {deviatedPct > 0 && (
              <div
                className={ADHERENCE_CONFIG.DEVIATED.barClassName}
                style={{ width: `${deviatedPct}%` }}
              />
            )}
          </div>

          <div className="flex justify-between text-[11px] text-muted-foreground tabular-nums">
            <span>{followedPct}%</span>
            <span>{deviatedPct}%</span>
          </div>
        </div>
      )}

      {judged > 0 && unknownCount > 0 && (
        <div className={cn("rounded-xl border p-2.5 flex gap-2 items-start", SEMANTIC_COLORS.warning.bgSoft, SEMANTIC_COLORS.warning.borderSoft)}>
          <AlertTriangle className={cn("w-3.5 h-3.5 shrink-0 mt-0.5", SEMANTIC_COLORS.warning.text)} />
          <p className={cn("text-[12px] leading-snug", SEMANTIC_COLORS.warning.text)}>
            미입력 {unknownCount}건
            {unknownPnL !== 0 && ` (${formatPnL(unknownPnL)})`}
            은 통계에서 제외
          </p>
        </div>
      )}
    </div>
  );
}
