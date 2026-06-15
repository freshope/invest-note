"use client";

import type { ConcentrationData } from "@/lib/analysis/concentration";
import { HHI_HIGH, HHI_MID } from "@/lib/constants/analysis";
import { COUNTRY_LABEL, isCountryCode } from "@/lib/constants/market";
import { MARKET_LABELS } from "@/lib/constants/trading";
import { PNL_COLORS } from "@/lib/constants/colors";
import { ProgressTrack } from "@/components/shared/ProgressTrack";

function WeightBar({ label, weight }: { label: string; weight: number }) {
  const pct = Math.round(weight * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[12px]">
        <span className="text-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">{pct}%</span>
      </div>
      <ProgressTrack pct={pct} colorClass="bg-[var(--chart-1)]" />
    </div>
  );
}

interface DiversificationPanelProps {
  concentration: ConcentrationData;
}

export function DiversificationPanel({ concentration }: DiversificationPanelProps) {
  const { hhi, top3, byCountry, byMarket } = concentration;
  const hhiPct = Math.round(hhi * 100);

  const hhiLabel =
    hhi > HHI_HIGH ? "집중" : hhi > HHI_MID ? "보통" : "분산";
  const hhiColor =
    hhi > HHI_HIGH
      ? PNL_COLORS.fall.text
      : hhi > HHI_MID
        ? "text-amber-500"
        : PNL_COLORS.rise.text;

  return (
    <div className="space-y-4">
      {/* HHI */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[12px] text-muted-foreground">집중도 지수 (HHI)</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            현재 보유 종목 기준 · 0에 가까울수록 분산
          </p>
        </div>
        <div className="text-right">
          <p className={`text-[20px] font-bold tabular-nums ${hhiColor}`}>
            {(hhi).toFixed(2)}
          </p>
          <p className={`text-[11px] font-semibold ${hhiColor}`}>{hhiLabel}</p>
        </div>
      </div>

      {/* 상위 3종목 */}
      {top3.length > 0 && (
        <div className="space-y-2">
          <p className="text-[12px] font-semibold text-muted-foreground">상위 종목</p>
          {top3.map((item) => (
            <WeightBar key={item.asset} label={item.asset} weight={item.weight} />
          ))}
        </div>
      )}

      {/* 국가 */}
      {byCountry.length > 1 && (
        <div className="space-y-2">
          <p className="text-[12px] font-semibold text-muted-foreground">국가</p>
          {byCountry.map((c) => (
            <WeightBar key={c.code} label={isCountryCode(c.code) ? COUNTRY_LABEL[c.code] : c.code} weight={c.weight} />
          ))}
        </div>
      )}

      {/* 자산군 */}
      {byMarket.length > 1 && (
        <div className="space-y-2">
          <p className="text-[12px] font-semibold text-muted-foreground">자산군</p>
          {byMarket.map((m) => (
            <WeightBar key={m.type} label={MARKET_LABELS[m.type as keyof typeof MARKET_LABELS] ?? m.type} weight={m.weight} />
          ))}
        </div>
      )}

      {hhiPct === 0 && (
        <p className="text-[12px] text-muted-foreground text-center py-2">
          현재 보유 중인 종목이 없습니다
        </p>
      )}
    </div>
  );
}
