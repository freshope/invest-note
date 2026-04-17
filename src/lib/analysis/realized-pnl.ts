import type { Trade } from "@/types/database";

// 각 SELL trade.id → 실현손익 (profit_loss 직접 입력값 우선, 없으면 WAC 기반 fallback)
export function computeRealizedPnL(trades: Trade[]): Map<string, number> {
  const result = new Map<string, number>();

  const sorted = [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
  );

  const posMap = new Map<string, { runningQty: number; runningCost: number }>();

  for (const trade of sorted) {
    const key = `${trade.ticker_symbol ?? trade.asset_name}:${trade.country_code}`;
    if (!posMap.has(key)) posMap.set(key, { runningQty: 0, runningCost: 0 });
    const pos = posMap.get(key)!;

    if (trade.trade_type === "BUY") {
      pos.runningQty += trade.quantity;
      pos.runningCost += trade.price * trade.quantity + trade.commission;
    } else {
      const avgCost = pos.runningQty > 0 ? pos.runningCost / pos.runningQty : 0;
      const pnl =
        trade.profit_loss != null
          ? Number(trade.profit_loss)
          : trade.price * trade.quantity - avgCost * trade.quantity - trade.commission - trade.tax;

      result.set(trade.id, pnl);

      pos.runningCost = Math.max(0, pos.runningCost - avgCost * trade.quantity);
      pos.runningQty = Math.max(0, pos.runningQty - trade.quantity);
    }
  }

  return result;
}
