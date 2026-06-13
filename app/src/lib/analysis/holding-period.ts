import type { Trade } from "@/types/database";
import { TRADE_TYPE } from "@/lib/constants/trading";

// 각 SELL trade.id → 저장된 보유 기간(일)
export function computeHoldingDays(trades: Trade[]): Map<string, number> {
  const result = new Map<string, number>();

  for (const trade of trades) {
    if (trade.trade_type === TRADE_TYPE.SELL && trade.holding_days != null) {
      result.set(trade.id, trade.holding_days);
    }
  }

  return result;
}
