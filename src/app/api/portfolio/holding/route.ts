import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { computeTotalHolding } from "@/lib/holdings";
import type { Trade } from "@/types/database";

export async function GET(req: NextRequest) {
  try {
    const { supabase, user } = await requireUser();
    const { searchParams } = req.nextUrl;

    const accountId = searchParams.get("accountId") ?? "";
    const ticker = searchParams.get("ticker") || null;
    const assetName = searchParams.get("assetName") ?? "";
    const country = searchParams.get("country") ?? "KR";

    if (!accountId || !assetName) return jsonError("accountId, assetName은 필수입니다.", 400);

    const { data: tradesRaw, error } = await supabase
      .from("trades")
      .select("trade_type, quantity, price, ticker_symbol, asset_name, country_code, account_id, traded_at")
      .eq("user_id", user.id)
      .order("traded_at", { ascending: true });

    if (error) return jsonError("거래 데이터를 불러올 수 없습니다.", 500);
    const trades = (tradesRaw ?? []) as Trade[];

    const quantity = computeTotalHolding(trades, { ticker, assetName, country, accountId });

    // WAC 평균 매수가 계산 (계좌 + flexible ticker 기준, computeTotalHolding과 동일 범위)
    const targetTicker = ticker ?? assetName;
    let runningQty = 0;
    let runningCost = 0;

    for (const trade of trades) {
      if (trade.account_id !== accountId) continue;
      const tradeCountry = trade.country_code ?? "KR";
      if (tradeCountry !== country) continue;
      const tradeTicker = trade.ticker_symbol ?? trade.asset_name;
      if (tradeTicker !== targetTicker && trade.asset_name !== assetName) continue;

      if (trade.trade_type === "BUY") {
        runningQty += trade.quantity;
        runningCost += trade.price * trade.quantity;
      } else {
        const avgCost = runningQty > 0 ? runningCost / runningQty : 0;
        const matched = Math.min(trade.quantity, runningQty);
        runningCost = Math.max(0, runningCost - avgCost * matched);
        runningQty = Math.max(0, runningQty - matched);
      }
    }

    const avgBuyPrice = runningQty > 0 ? runningCost / runningQty : null;

    return NextResponse.json({ quantity, avgBuyPrice });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
