import { toKST } from "@/lib/trade-utils";
import { computeRealizedPnL, sellPnL } from "@/lib/analysis/realized-pnl";
import type { Trade, Account } from "@/types/database";

export type QuoteMap = Record<string, { price: number; currency: string; asOf: string } | null>;

export interface Position {
  key: string;                  // `${ticker}:${country}`
  ticker: string;
  country: string;
  assetName: string;
  holdingQuantity: number;      // sum(buy.qty) - sum(sell.qty)
  avgBuyPrice: number;          // WAC: sum(buy.price*qty) / sum(buy.qty)
  costBasis: number;            // avgBuyPrice * holdingQuantity
  realizedPnL: number;          // 매도 실현손익 합계 (profit_loss 입력값 우선, 없으면 WAC fallback)
  currentPrice: number | null;
  evaluation: number | null;    // currentPrice * holdingQuantity
  unrealizedPnL: number | null; // evaluation - costBasis
  lastNoteType: "근거" | "회고" | null;
  lastNote: string | null;
  lastTradedAt: string;
  accountIds: string[];
}

export interface AccountSnapshot {
  account: Account;
  stockEvaluation: number;
  cashBalance: number;
  totalValue: number;
}

export interface DashboardTotals {
  totalEvaluation: number;
  totalUnrealizedPnL: number;
  totalRealizedPnL: number;
  totalCash: number;
  totalAssets: number;
  monthRealizedPnL: number;
  monthTradeCount: number;
  missingQuoteTickers: string[];
}

export function buildPositions(trades: Trade[]): Position[] {
  const map = new Map<string, {
    ticker: string;
    country: string;
    assetName: string;
    runningQty: number;   // 현재 보유 수량 (매수 - 매도 누적)
    runningCost: number;  // 현재 보유분의 취득 원가 합계 (부분 매도 시 비례 차감)
    realizedPnL: number;
    lastTradedAt: string;
    accountIds: Set<string>;
    lastNoteType: "근거" | "회고" | null;
    lastNote: string | null;
  }>();

  // Oldest first — iterating once, last write per key = newest note
  const sorted = [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
  );

  for (const trade of sorted) {
    const ticker = trade.ticker_symbol ?? trade.asset_name;
    const country = trade.country_code ?? "KR";
    const key = `${ticker}:${country}`;

    if (!map.has(key)) {
      map.set(key, {
        ticker,
        country,
        assetName: trade.asset_name,
        runningQty: 0,
        runningCost: 0,
        realizedPnL: 0,
        lastTradedAt: trade.traded_at,
        accountIds: new Set(),
        lastNoteType: null,
        lastNote: null,
      });
    }

    const pos = map.get(key)!;
    pos.lastTradedAt = trade.traded_at;
    pos.accountIds.add(trade.account_id);

    if (trade.trade_type === "BUY") {
      pos.runningQty += trade.quantity;
      pos.runningCost += trade.price * trade.quantity;
      const reason = trade.buy_reason?.trim();
      if (reason) { pos.lastNoteType = "근거"; pos.lastNote = reason; }
    } else {
      // 매도 시 보유 원가를 평균단가 비례로 차감 (running WAC)
      const avgCost = pos.runningQty > 0 ? pos.runningCost / pos.runningQty : 0;
      const matchedQty = Math.min(trade.quantity, pos.runningQty);
      pos.realizedPnL += sellPnL(trade, avgCost, matchedQty);
      pos.runningCost = Math.max(0, pos.runningCost - avgCost * matchedQty);
      pos.runningQty = Math.max(0, pos.runningQty - trade.quantity);
      const note = trade.reflection_note?.trim() || trade.sell_reason?.trim();
      if (note) { pos.lastNoteType = "회고"; pos.lastNote = note; }
    }
  }

  const positions: Position[] = [];

  for (const [key, pos] of map.entries()) {
    const holdingQuantity = pos.runningQty;
    if (holdingQuantity <= 0) continue; // 전량 매도된 종목 제외

    const avgBuyPrice = holdingQuantity > 0 ? pos.runningCost / holdingQuantity : 0;
    const costBasis = pos.runningCost;
    positions.push({
      key,
      ticker: pos.ticker,
      country: pos.country,
      assetName: pos.assetName,
      holdingQuantity,
      avgBuyPrice,
      costBasis,
      realizedPnL: pos.realizedPnL,
      currentPrice: null,
      evaluation: null,
      unrealizedPnL: null,
      lastNoteType: pos.lastNoteType,
      lastNote: pos.lastNote,
      lastTradedAt: pos.lastTradedAt,
      accountIds: Array.from(pos.accountIds),
    });
  }

  return positions;
}

export function mergeQuotes(positions: Position[], quotes: QuoteMap): Position[] {
  return positions.map((pos) => {
    const quote = quotes[pos.key] ?? null;
    if (!quote) return pos;
    const evaluation = quote.price * pos.holdingQuantity;
    return {
      ...pos,
      currentPrice: quote.price,
      evaluation,
      unrealizedPnL: evaluation - pos.costBasis,
    };
  });
}

export function buildAccountSnapshots(
  accounts: Account[],
  trades: Trade[],
  quotes: QuoteMap,
): AccountSnapshot[] {
  const byAccount = new Map<string, Trade[]>();
  for (const t of trades) {
    const list = byAccount.get(t.account_id);
    if (list) list.push(t);
    else byAccount.set(t.account_id, [t]);
  }

  return accounts.map((account) => {
    const accountTrades = byAccount.get(account.id) ?? [];
    const posMap = new Map<string, { qty: number; costBasis: number }>();

    for (const trade of accountTrades) {
      const ticker = trade.ticker_symbol ?? trade.asset_name;
      const key = `${ticker}:${trade.country_code ?? "KR"}`;
      if (!posMap.has(key)) posMap.set(key, { qty: 0, costBasis: 0 });
      const p = posMap.get(key)!;
      if (trade.trade_type === "BUY") {
        p.qty += trade.quantity;
        p.costBasis += trade.price * trade.quantity;
      } else {
        p.qty -= trade.quantity;
      }
    }

    let stockEvaluation = 0;
    for (const [key, { qty }] of posMap.entries()) {
      if (qty <= 0) continue;
      const quote = quotes[key] ?? null;
      if (quote) {
        stockEvaluation += quote.price * qty;
      }
    }

    return {
      account,
      stockEvaluation,
      cashBalance: account.cash_balance,
      totalValue: stockEvaluation + account.cash_balance,
    };
  });
}

export function buildTotals(
  positions: Position[],
  accounts: Account[],
  trades: Trade[],
): DashboardTotals {
  const totalEvaluation = positions.reduce((s, p) => s + (p.evaluation ?? 0), 0);
  const totalUnrealizedPnL = positions.reduce((s, p) => s + (p.unrealizedPnL ?? 0), 0);
  const totalCash = accounts.reduce((s, a) => s + a.cash_balance, 0);

  const now = toKST(new Date());
  const thisYear = now.getFullYear();
  const thisMonth = now.getMonth();

  const pnlMap = computeRealizedPnL(trades);

  let totalRealizedPnL = 0;
  let monthRealizedPnL = 0;
  let monthTradeCount = 0;
  for (const trade of trades) {
    if (trade.trade_type === "SELL") {
      totalRealizedPnL += pnlMap.get(trade.id) ?? 0;
    }
    const kst = toKST(new Date(trade.traded_at));
    if (kst.getFullYear() === thisYear && kst.getMonth() === thisMonth) {
      monthTradeCount++;
      if (trade.trade_type === "SELL") {
        monthRealizedPnL += pnlMap.get(trade.id) ?? 0;
      }
    }
  }

  const missingQuoteTickers = positions
    .filter((p) => p.currentPrice === null)
    .map((p) => p.assetName);

  return {
    totalEvaluation,
    totalUnrealizedPnL,
    totalRealizedPnL,
    totalCash,
    totalAssets: totalEvaluation + totalCash,
    monthRealizedPnL,
    monthTradeCount,
    missingQuoteTickers,
  };
}
