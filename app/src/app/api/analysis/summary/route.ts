import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { HttpError } from "@/lib/api-server/errors";
import { fetchUserTradesWithPeriod } from "@/lib/api-server/analysis-context";
import { computeSummary } from "@/lib/analysis/aggregate";
import { buildPnlMap } from "@/lib/analysis/realized-pnl";
import { computeHoldingDays } from "@/lib/analysis/holding-period";

export async function GET(req: NextRequest) {
  try {
    const { allTrades, trades, period } = await fetchUserTradesWithPeriod(req);

    // WAC/FIFO 모두 전체 trades 기준 (기간 이전 매수 포함해야 정확)
    const pnlMap = buildPnlMap(allTrades);
    const holdingDaysMap = computeHoldingDays(allTrades);
    const summary = computeSummary(trades, pnlMap, holdingDaysMap, allTrades);

    return NextResponse.json({ period, ...summary });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    console.error("[analysis/summary]", e);
    return NextResponse.json({ error: "서버 오류가 발생했습니다." }, { status: 500 });
  }
}
