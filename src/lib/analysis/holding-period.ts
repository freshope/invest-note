import type { Trade } from "@/types/database";
import { toKST } from "@/lib/trade-utils";

// 각 SELL trade.id → FIFO 기준 가중평균 보유 기간(일)
export function computeHoldingDays(trades: Trade[]): Map<string, number> {
  const result = new Map<string, number>();

  const sorted = [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
  );

  // 종목별 FIFO 큐: { qty, tradedAt }
  const queueMap = new Map<string, { qty: number; tradedAt: string }[]>();

  for (const trade of sorted) {
    const key = `${trade.ticker_symbol ?? trade.asset_name}:${trade.country_code}`;
    if (!queueMap.has(key)) queueMap.set(key, []);
    const queue = queueMap.get(key)!;

    if (trade.trade_type === "BUY") {
      queue.push({ qty: trade.quantity, tradedAt: trade.traded_at });
    } else {
      let remaining = trade.quantity;
      const sellTime = toKST(new Date(trade.traded_at)).getTime();

      let weightedDays = 0;
      let totalConsumed = 0;

      while (remaining > 0 && queue.length > 0) {
        const slot = queue[0];
        const consume = Math.min(slot.qty, remaining);
        const buyTime = toKST(new Date(slot.tradedAt)).getTime();
        const days = (sellTime - buyTime) / (1000 * 60 * 60 * 24);

        weightedDays += days * consume;
        totalConsumed += consume;
        remaining -= consume;
        slot.qty -= consume;
        if (slot.qty <= 0) queue.shift();
      }

      result.set(trade.id, totalConsumed > 0 ? Math.round(weightedDays / totalConsumed) : 0);
    }
  }

  return result;
}
