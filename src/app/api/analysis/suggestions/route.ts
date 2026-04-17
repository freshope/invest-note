import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { HttpError } from "@/lib/api-server/errors";
import { parsePeriod, filterByPeriod } from "@/lib/analysis/period";
import { computeSummary } from "@/lib/analysis/aggregate";
import { computeConcentration } from "@/lib/analysis/concentration";
import { computeProfile } from "@/lib/analysis/profile";
import { buildPositions, mergeQuotes } from "@/lib/portfolio";
import { fetchQuotesByKeys } from "@/lib/quotes";
import { evaluateRules } from "@/lib/analysis/rules";
import type { Trade } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

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

    const positions0 = buildPositions(allTrades as TradeWithAccount[]);
    const quotes = await fetchQuotesByKeys(positions0.map((p) => p.key));
    const positions = mergeQuotes(positions0, quotes);

    const summary = computeSummary(trades);
    const concentration = computeConcentration(positions, allTrades);
    const { profile } = computeProfile(trades, concentration.hhi);

    const suggestions = evaluateRules({ summary, profile, concentration });

    return NextResponse.json({ period, suggestions });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return NextResponse.json({ error: "서버 오류가 발생했습니다." }, { status: 500 });
  }
}
