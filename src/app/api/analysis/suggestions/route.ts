import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { HttpError } from "@/lib/api-server/errors";
import { fetchUserTradesWithPeriod } from "@/lib/api-server/analysis-context";
import { computeSummary } from "@/lib/analysis/aggregate";
import { computeRealizedPnL } from "@/lib/analysis/realized-pnl";
import { computeHoldingDays } from "@/lib/analysis/holding-period";
import { computeConcentration } from "@/lib/analysis/concentration";
import { computeProfile } from "@/lib/analysis/profile";
import { buildPositions } from "@/lib/portfolio";
import { evaluateRules } from "@/lib/analysis/rules";

export async function GET(req: NextRequest) {
  try {
    const { allTrades, trades, period } = await fetchUserTradesWithPeriod(req);

    // 외부 시세 호출 없이 costBasis 기준으로 집중도 계산
    const positions = buildPositions(allTrades);
    const concentration = computeConcentration(positions, allTrades);

    // WAC/FIFO 모두 전체 trades 기준 (기간 이전 매수 포함해야 정확)
    const pnlMap = computeRealizedPnL(allTrades);
    const holdingDaysMap = computeHoldingDays(allTrades);
    const summary = computeSummary(trades, pnlMap, holdingDaysMap, allTrades);
    const { profile } = computeProfile(trades, concentration.hhi, holdingDaysMap);

    const suggestions = evaluateRules({ summary, profile, concentration });

    return NextResponse.json({ period, suggestions });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    console.error("[analysis/suggestions]", e);
    return NextResponse.json({ error: "서버 오류가 발생했습니다." }, { status: 500 });
  }
}
