import type { SupabaseClient } from "@supabase/supabase-js";
import type { Trade } from "@/types/database";
import { computeGroupPnL, type TradeGroupKey } from "@/lib/analysis/realized-pnl";

// 해당 그룹의 SELL들 profit_loss를 재계산하여 DB 업데이트
// 옵션 B: 개별 UPDATE 실패 시 콘솔 로그만 남기고 계속 (트랜잭션 미지원 대응)
export async function recalcGroupPnL(
  supabase: SupabaseClient,
  userId: string,
  trades: Trade[],
  key: TradeGroupKey,
): Promise<void> {
  const pnlMap = computeGroupPnL(trades, key);

  const updates = Array.from(pnlMap.entries()).map(([sellId, entry]) =>
    supabase
      .from("trades")
      .update({ profit_loss: entry.profit_loss, avg_buy_price: entry.avg_buy_price })
      .eq("id", sellId)
      .eq("user_id", userId),
  );

  const results = await Promise.all(updates);
  for (const { error } of results) {
    if (error) console.error("[pnl-sync] profit_loss 갱신 실패:", error.message);
  }
}

// 거래 목록에서 해당 그룹 키 추출
export function tradeToGroupKey(trade: Pick<Trade, "ticker_symbol" | "asset_name" | "country_code" | "account_id">): TradeGroupKey {
  return {
    ticker: trade.ticker_symbol,
    assetName: trade.asset_name,
    country: trade.country_code ?? "KR",
    accountId: trade.account_id,
  };
}
