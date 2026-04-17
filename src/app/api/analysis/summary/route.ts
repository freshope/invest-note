import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { HttpError } from "@/lib/api-server/errors";
import { parsePeriod, filterByPeriod } from "@/lib/analysis/period";
import { computeSummary } from "@/lib/analysis/aggregate";
import { computeRealizedPnL } from "@/lib/analysis/realized-pnl";
import { computeHoldingDays } from "@/lib/analysis/holding-period";
import type { Trade } from "@/types/database";

export async function GET(req: NextRequest) {
  try {
    const { supabase, user } = await requireUser();
    const period = parsePeriod(req.nextUrl.searchParams.get("period"));

    const { data: tradesRaw } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .order("traded_at", { ascending: true });

    const allTrades = (tradesRaw ?? []) as Trade[];
    const trades = filterByPeriod(allTrades, period);

    // WAC 계산은 전체 trades 기준 (기간 이전 매수 포함)
    const pnlMap = computeRealizedPnL(allTrades);
    const holdingDaysMap = computeHoldingDays(trades);
    const summary = computeSummary(trades, pnlMap, holdingDaysMap);

    return NextResponse.json({ period, ...summary });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return NextResponse.json({ error: "서버 오류가 발생했습니다." }, { status: 500 });
  }
}
