import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { evaluateStrategyAdherence } from "@/lib/analysis/strategy-adherence";
import {
  findLatestBuyStrategy,
  computeFlexibleBreakdown,
  computeFlexibleHoldingDays,
} from "@/lib/holdings";
import type { Trade, TradeResult } from "@/types/database";

export type { SellBreakdown } from "@/lib/holdings";

function derivedResult(pnl: number): TradeResult {
  if (pnl > 0) return "SUCCESS";
  if (pnl < 0) return "FAIL";
  return "BREAKEVEN";
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const { data: target, error: fetchError } = await supabase
      .from("trades")
      .select("*")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (fetchError || !target) return jsonError("거래를 찾을 수 없습니다.", 404);
    if ((target as Trade).trade_type !== "SELL") return jsonError("매도 거래만 조회할 수 있습니다.", 400);

    const sell = target as Trade;

    const { data: allTradesRaw, error: allErr } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .order("traded_at", { ascending: true });

    if (allErr) return jsonError("거래 데이터를 불러올 수 없습니다.", 500);
    const allTrades = (allTradesRaw ?? []) as Trade[];

    const breakdown = computeFlexibleBreakdown(sell, allTrades);
    const holdingDays = computeFlexibleHoldingDays(sell, allTrades);

    const ticker = sell.ticker_symbol ?? sell.asset_name;
    const country = sell.country_code ?? "KR";
    const plannedStrategy = findLatestBuyStrategy(allTrades, {
      ticker,
      country,
      accountId: sell.account_id,
    });

    const strategyEval =
      holdingDays != null
        ? evaluateStrategyAdherence(plannedStrategy, holdingDays)
        : null;

    return NextResponse.json({
      pnl: breakdown.pnl,
      result: derivedResult(breakdown.pnl),
      holdingDays,
      strategyEvaluation: strategyEval,
      breakdown,
    });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
