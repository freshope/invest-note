import { toKST } from "@/lib/trade-utils";
import { buildPnlMap } from "@/lib/analysis/realized-pnl";
import type { Trade, Account } from "@/types/database";

export type QuoteMap = Record<string, { price: number; currency: string; asOf: string } | null>;

export interface Position {
  key: string;                  // `${ticker}:${country}`
  ticker: string;
  country: string;
  assetName: string;
  exchange: string;
  holdingQuantity: number;      // sum(buy.qty) - sum(sell.qty)
  avgBuyPrice: number;          // WAC: sum(buy.price*qty) / sum(buy.qty)
  costBasis: number;            // avgBuyPrice * holdingQuantity
  currentPrice: number | null;
  evaluation: number | null;    // currentPrice * holdingQuantity
  unrealizedPnL: number | null; // evaluation - costBasis
  lastNote: string | null;      // 가장 최근 BUY 거래의 buy_reason
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
  // 계좌별 lot 추적 — 키: ticker:country:accountId
  // 다른 계좌의 매도가 A 계좌 매수에 매칭되는 오염 방지
  const lotMap = new Map<string, {
    ticker: string;
    country: string;
    assetName: string;
    accountId: string;
    exchange: string;
    runningQty: number;
    runningCost: number;
    lastTradedAt: string;
    lastNote: string | null;
  }>();

  // Oldest first — iterating once, last write per key = newest note
  const sorted = [...trades].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
  );

  for (const trade of sorted) {
    const ticker = trade.ticker_symbol ?? trade.asset_name;
    const country = trade.country_code ?? "KR";
    const lotKey = `${ticker}:${country}:${trade.account_id}`;

    if (!lotMap.has(lotKey)) {
      lotMap.set(lotKey, {
        ticker,
        country,
        assetName: trade.asset_name,
        accountId: trade.account_id,
        exchange: trade.exchange,
        runningQty: 0,
        runningCost: 0,
        lastTradedAt: trade.traded_at,
        lastNote: null,
      });
    }

    const lot = lotMap.get(lotKey)!;
    lot.lastTradedAt = trade.traded_at;
    // 빈 문자열이면 이전 lot의 거래소 값을 보존 (자동완성 없이 입력된 거래 방어)
    if (trade.exchange) lot.exchange = trade.exchange;

    if (trade.trade_type === "BUY") {
      lot.runningQty += trade.quantity;
      lot.runningCost += trade.price * trade.quantity;
      const reason = trade.buy_reason?.trim();
      if (reason) lot.lastNote = reason;
    } else {
      const avgCost = Number(trade.avg_buy_price ?? 0);
      const matchedQty = Math.min(trade.quantity, lot.runningQty);
      lot.runningCost = Math.max(0, lot.runningCost - avgCost * matchedQty);
      lot.runningQty = Math.max(0, lot.runningQty - trade.quantity);
    }
  }

  // 계좌별 lot → 종목별(ticker:country) 집계 포지션
  const posMap = new Map<string, {
    ticker: string;
    country: string;
    assetName: string;
    exchange: string;
    runningQty: number;
    runningCost: number;
    lastTradedAt: string;
    accountIds: Set<string>;
    lastNote: string | null;
  }>();

  for (const lot of lotMap.values()) {
    if (lot.runningQty <= 0) continue;
    const displayKey = `${lot.ticker}:${lot.country}`;
    if (!posMap.has(displayKey)) {
      posMap.set(displayKey, {
        ticker: lot.ticker,
        country: lot.country,
        assetName: lot.assetName,
        exchange: lot.exchange,
        runningQty: 0,
        runningCost: 0,
        lastTradedAt: lot.lastTradedAt,
        accountIds: new Set(),
        lastNote: null,
      });
    }
    const pos = posMap.get(displayKey)!;
    pos.runningQty += lot.runningQty;
    pos.runningCost += lot.runningCost;
    if (lot.lastTradedAt > pos.lastTradedAt) pos.lastTradedAt = lot.lastTradedAt;
    if (lot.exchange) pos.exchange = lot.exchange;
    pos.accountIds.add(lot.accountId);
    if (lot.lastNote) pos.lastNote = lot.lastNote;
  }

  const positions: Position[] = [];

  for (const [key, pos] of posMap.entries()) {
    const holdingQuantity = pos.runningQty;
    const avgBuyPrice = holdingQuantity > 0 ? pos.runningCost / holdingQuantity : 0;
    positions.push({
      key,
      ticker: pos.ticker,
      country: pos.country,
      assetName: pos.assetName,
      exchange: pos.exchange,
      holdingQuantity,
      avgBuyPrice,
      costBasis: pos.runningCost,
      currentPrice: null,
      evaluation: null,
      unrealizedPnL: null,
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

  const pnlMap = buildPnlMap(trades);

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
