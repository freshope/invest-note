"use client";

import { AlertTriangle, Info, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AnalysisSummary } from "@/lib/analysis/aggregate";

export interface Insight {
  id: string;
  severity: "info" | "warn" | "critical";
  title: string;
  body: string;
}

const SEVERITY_STYLES = {
  info: {
    bg: "bg-blue-50 dark:bg-blue-950/30",
    border: "border-blue-200 dark:border-blue-800",
    icon: Info,
    iconClass: "text-blue-500",
  },
  warn: {
    bg: "bg-amber-50 dark:bg-amber-950/30",
    border: "border-amber-200 dark:border-amber-800",
    icon: AlertTriangle,
    iconClass: "text-amber-500",
  },
  critical: {
    bg: "bg-red-50 dark:bg-red-950/30",
    border: "border-red-200 dark:border-red-800",
    icon: AlertCircle,
    iconClass: "text-red-500",
  },
};

// Phase A seed: summary 데이터 기반으로 인사이트 생성
export function seedInsights(summary: AnalysisSummary): Insight[] {
  const insights: Insight[] = [];

  if (summary.feelingRate >= 40 && summary.totalTrades >= 5) {
    insights.push({
      id: "feeling_heavy",
      severity: "warn",
      title: "근거 없는 매수 비율이 높아요",
      body: `전체 매수 중 '감/직감'으로 진입한 비율이 ${Math.round(summary.feelingRate)}%입니다. 기술적 근거를 1개 이상 추가해보세요.`,
    });
  }

  if (summary.reflectionRate < 30 && summary.sellTrades >= 3) {
    insights.push({
      id: "no_reflection",
      severity: "info",
      title: "매도 후 회고가 드물어요",
      body: `매도 ${summary.sellTrades}건 중 회고 작성률이 ${Math.round(summary.reflectionRate)}%입니다. 최근 매도 거래에 회고를 남겨보세요.`,
    });
  }

  if (summary.resultInputRate < 50 && summary.sellTrades >= 3) {
    insights.push({
      id: "result_missing",
      severity: "info",
      title: "거래 결과 입력이 부족해요",
      body: `매도 거래 중 ${Math.round(100 - summary.resultInputRate)}%에 결과(성공/실패)가 미입력되어 승률 분석 정확도가 낮습니다.`,
    });
  }

  if (summary.winRate >= 65 && summary.sellTrades >= 5 && summary.resultInputRate >= 50) {
    insights.push({
      id: "high_winrate",
      severity: "info",
      title: "좋은 승률을 유지하고 있어요",
      body: `현재 승률 ${Math.round(summary.winRate)}%로 좋은 성과를 내고 있습니다. 지금의 매매 패턴을 유지해보세요.`,
    });
  }

  return insights.slice(0, 3);
}

interface InsightHighlightsProps {
  insights: Insight[];
}

export function InsightHighlights({ insights }: InsightHighlightsProps) {
  if (insights.length === 0) return null;

  return (
    <div className="space-y-2">
      {insights.map((insight) => {
        const style = SEVERITY_STYLES[insight.severity];
        const Icon = style.icon;
        return (
          <div
            key={insight.id}
            className={cn("rounded-2xl border p-3.5 flex gap-3", style.bg, style.border)}
          >
            <Icon className={cn("w-4 h-4 shrink-0 mt-0.5", style.iconClass)} />
            <div className="space-y-0.5">
              <p className="text-[13px] font-semibold text-foreground">{insight.title}</p>
              <p className="text-[12px] text-muted-foreground leading-snug">{insight.body}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
