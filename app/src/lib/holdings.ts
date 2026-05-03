import type { Trade, StrategyType } from "@/types/database";
import { toKST } from "@/lib/trade-utils";

export interface LotKey {
  ticker: string;
  country: string;
  accountId: string;
  assetName?: string; // flexible 매칭용 — 없으면 ticker와 동일하게 취급
}

export interface SellBreakdown {
  sellPrice: number;
  quantity: number;      // 실제 매칭된 수량
  avgCostPrice: number;  // WAC 평균 매수가
  sellAmount: number;    // sellPrice × quantity
  costBasis: number;     // avgCostPrice × quantity
  commission: number;
  tax: number;
  pnl: number;
}

// ─────────────────────────────────────────────
// 공용 lot 매칭 유틸
// ─────────────────────────────────────────────

// 계좌 + country + (ticker OR asset_name) 기준 매칭.
// ticker_symbol 불일치 데이터(null vs "035420")를 동일 종목으로 취급.
// 계좌는 lot 분리 기준으로 유지 — buildPositions, 검증, breakdown이 일관된 범위를 공유.
function isFlexibleMatch(
  trade: Trade,
  targetCountry: string,
  targetTicker: string,   // sell.ticker_symbol ?? sell.asset_name
  targetAsset: string,    // sell.asset_name
  targetAccountId: string,
): boolean {
  if (trade.account_id !== targetAccountId) return false;
  const tradeCountry = trade.country_code ?? "KR";
  if (tradeCountry !== targetCountry) return false;
  const tradeTicker = trade.ticker_symbol ?? trade.asset_name;
  return tradeTicker === targetTicker || trade.asset_name === targetAsset;
}

function sortByTradedAt(trades: Trade[]): Trade[] {
  return [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
  );
}

// ─────────────────────────────────────────────
// Strict per-lot (ticker:country:accountId) — 전략 상속 전용
// ─────────────────────────────────────────────

export function computeLotQuantity(trades: Trade[], key: LotKey): number {
  const lotKey = `${key.ticker}:${key.country}:${key.accountId}`;
  let runningQty = 0;

  for (const trade of sortByTradedAt(trades)) {
    const tradeKey = `${trade.ticker_symbol ?? trade.asset_name}:${trade.country_code ?? "KR"}:${trade.account_id}`;
    if (tradeKey !== lotKey) continue;
    if (trade.trade_type === "BUY") runningQty += trade.quantity;
    else runningQty = Math.max(0, runningQty - trade.quantity);
  }

  return runningQty;
}

export function findLatestBuyStrategy(trades: Trade[], key: LotKey): StrategyType | null {
  const assetName = key.assetName ?? key.ticker;

  const buys = trades
    .filter((t) =>
      t.trade_type === "BUY" &&
      isFlexibleMatch(t, key.country, key.ticker, assetName, key.accountId),
    )
    .sort((a, b) => new Date(b.traded_at).getTime() - new Date(a.traded_at).getTime());

  return buys[0]?.strategy_type ?? null;
}

// ─────────────────────────────────────────────
// Flexible (ticker OR asset_name) + 계좌 스코프
// ─────────────────────────────────────────────

// 서버 SELL 검증용: 동일 계좌 내 flexible 매칭으로 보유량 반환.
// computeFlexibleBreakdown과 동일한 lot 범위를 공유 → 검증 통과 시 breakdown도 정확.
export function computeTotalHolding(
  trades: Trade[],
  key: { ticker: string | null; assetName: string; country: string; accountId: string },
): number {
  const targetCountry = key.country;
  const targetTicker = key.ticker ?? key.assetName;
  const targetAsset = key.assetName;

  let runningQty = 0;

  for (const trade of sortByTradedAt(trades)) {
    if (!isFlexibleMatch(trade, targetCountry, targetTicker, targetAsset, key.accountId)) continue;
    if (trade.trade_type === "BUY") runningQty += trade.quantity;
    else runningQty = Math.max(0, runningQty - trade.quantity);
  }

  return runningQty;
}

// 저장된 avg_buy_price / profit_loss 기반 breakdown 구성 — 정합성은 recalcGroupPnL이 보장
export function computeFlexibleBreakdown(sell: Trade): SellBreakdown {
  const avgCostPrice = Number(sell.avg_buy_price ?? 0);
  const quantity = sell.quantity;
  const sellAmount = sell.price * quantity;
  const costBasis = avgCostPrice * quantity;
  return {
    sellPrice: sell.price,
    quantity,
    avgCostPrice,
    sellAmount,
    costBasis,
    commission: sell.commission,
    tax: sell.tax,
    pnl: Number(sell.profit_loss ?? 0),
  };
}

// FIFO 가중평균 보유일수 (동일 계좌 + flexible ticker).
export function computeFlexibleHoldingDays(sell: Trade, allTrades: Trade[]): number | null {
  const targetCountry = sell.country_code ?? "KR";
  const targetTicker = sell.ticker_symbol ?? sell.asset_name;
  const targetAsset = sell.asset_name;
  const targetAccountId = sell.account_id;
  const sellTimeMs = toKST(new Date(sell.traded_at)).getTime();

  const queue: { qty: number; timeMs: number }[] = [];

  for (const trade of sortByTradedAt(allTrades)) {
    if (trade.id === sell.id) {
      let remaining = sell.quantity;
      let weightedMs = 0;
      let totalConsumed = 0;

      for (const slot of queue) {
        if (remaining <= 0) break;
        const consume = Math.min(slot.qty, remaining);
        weightedMs += (sellTimeMs - slot.timeMs) * consume;
        totalConsumed += consume;
        remaining -= consume;
      }

      return totalConsumed > 0
        ? Math.round(weightedMs / totalConsumed / (1000 * 60 * 60 * 24))
        : null;
    }

    if (!isFlexibleMatch(trade, targetCountry, targetTicker, targetAsset, targetAccountId)) continue;

    if (trade.trade_type === "BUY") {
      queue.push({ qty: trade.quantity, timeMs: toKST(new Date(trade.traded_at)).getTime() });
    } else {
      let rem = trade.quantity;
      while (rem > 0 && queue.length > 0) {
        const consume = Math.min(queue[0].qty, rem);
        queue[0].qty -= consume;
        rem -= consume;
        if (queue[0].qty <= 0) queue.shift();
      }
    }
  }

  return null;
}
