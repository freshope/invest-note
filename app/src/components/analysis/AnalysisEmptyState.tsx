"use client";

import { BarChart2 } from "lucide-react";

interface AnalysisEmptyStateProps {
  hasTrades?: boolean;
  hasSells?: boolean;
}

export function AnalysisEmptyState({ hasTrades = false, hasSells = false }: AnalysisEmptyStateProps) {
  const message = !hasTrades
    ? "첫 거래를 기록하면 성향 분석이 생깁니다"
    : !hasSells
      ? "매도 기록이 생기면 승률과 손익 분석이 표시됩니다"
      : "선택한 기간에 데이터가 없습니다";

  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3 text-center px-8">
      <BarChart2 className="w-10 h-10 text-muted-foreground/40" />
      <p className="text-[14px] text-muted-foreground">{message}</p>
    </div>
  );
}
