import type { SupabaseClient } from "@supabase/supabase-js";
import type { Trade } from "@/types/database";
import { computeGroupPnL, tradeToGroupKey, type TradeGroupKey } from "@/lib/analysis/realized-pnl";

export { tradeToGroupKey };

// 개별 UPDATE 실패 시 콘솔 로그만 남기고 계속 (트랜잭션 미지원 대응)
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
