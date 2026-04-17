import type { Trade } from "@/types/database";

// profit_loss 입력값 우선, 없으면 WAC 기반 fallback: (매도가 × 매도수량) − (평균단가 × 매칭수량) − 수수료 − 세금
// costQty: 실제 보유 수량 기준 매칭 수량 — 미지정시 trade.quantity 사용 (oversell 방지용)
export function sellPnL(trade: Trade, avgCost: number, costQty?: number): number {
  if (trade.profit_loss != null) return Number(trade.profit_loss);
  const qty = costQty ?? trade.quantity;
  return trade.price * trade.quantity - avgCost * qty - trade.commission - trade.tax;
}

// 각 SELL trade.id → 실현손익
export function computeRealizedPnL(trades: Trade[]): Map<string, number> {
  const result = new Map<string, number>();

  const sorted = [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
  );

  const posMap = new Map<string, { runningQty: number; runningCost: number }>();

  for (const trade of sorted) {
    const key = `${trade.ticker_symbol ?? trade.asset_name}:${trade.country_code ?? "KR"}`;
    if (!posMap.has(key)) posMap.set(key, { runningQty: 0, runningCost: 0 });
    const pos = posMap.get(key)!;

    if (trade.trade_type === "BUY") {
      pos.runningQty += trade.quantity;
      pos.runningCost += trade.price * trade.quantity;
    } else {
      const avgCost = pos.runningQty > 0 ? pos.runningCost / pos.runningQty : 0;
      const matchedQty = Math.min(trade.quantity, pos.runningQty);
      result.set(trade.id, sellPnL(trade, avgCost, matchedQty));

      pos.runningCost = Math.max(0, pos.runningCost - avgCost * matchedQty);
      pos.runningQty = Math.max(0, pos.runningQty - trade.quantity);
    }
  }

  return result;
}
