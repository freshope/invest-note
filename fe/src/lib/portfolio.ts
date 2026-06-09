import { toKST } from "@/lib/trade-utils";
import { buildPnlMap, sortForCalc } from "@/lib/analysis/realized-pnl";
import { TRADE_TYPE } from "@/lib/constants/trading";
import { DEFAULT_COUNTRY_CODE } from "@/lib/constants/market";
import { currencyForCountry, toKRW } from "@/lib/format";
import type { Trade, Account } from "@/types/database";

/** 포지션 key "TICKER:COUNTRY" 에서 country 추출(없으면 KR). */
function countryFromKey(key: string): string {
  return key.split(":")[1] ?? DEFAULT_COUNTRY_CODE;
}

export type QuoteMap = Record<string, { price: number; currency: string; as_of: string } | null>;

export interface Position {
  key: string;                  // `${ticker}:${country}`
  ticker: string;
  country: string;
  currency: string;             // 거래 통화(KRW|USD) — 달러 보조 표시 분기용
  assetName: string;
  exchange: string;
  holdingQuantity: number;      // sum(buy.qty) - sum(sell.qty)
  avgBuyPrice: number;          // KRW (거래 시점 환율 고정, primary)
  avgBuyPriceNative: number;    // native(USD 등) — 달러 보조
  costBasis: number;            // KRW (primary)
  costBasisNative: number;      // native
  realizedPnL: number;          // KRW
  currentPrice: number | null;  // native 시세
  evaluation: number | null;    // KRW (= currentPrice × qty × 현재환율, primary)
  evaluationNative: number | null;  // native(= currentPrice × qty)
  unrealizedPnL: number | null; // KRW (= evaluation - costBasis)
  lastNote: string | null;      // 가장 최근 BUY 거래의 buy_reason
  lastTradedAt: string;
  accountIds: string[];
}

export interface AccountHolding {
  key: string;      // `${ticker}:${country}` — position.key 와 동일 규칙
  quantity: number;
}

export interface AccountSnapshot {
  account: Account;
  stockEvaluation: number;
  cashBalance: number;
  totalValue: number;
  holdings: AccountHolding[];
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

  // BE의 sort_for_calc와 동일 규칙(traded_at → BUY 먼저 → created_at).
  // 같은 날 BUY+SELL 일괄 등록 시 동률 traded_at 에서 SELL이 먼저 적용돼 보유 수량이 음수로 클램프되던 버그 방지.
  const sorted = sortForCalc(trades);

  for (const trade of sorted) {
    const ticker = trade.ticker_symbol ?? trade.asset_name;
    const country = trade.country_code ?? DEFAULT_COUNTRY_CODE;
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

    if (trade.trade_type === TRADE_TYPE.BUY) {
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
    // NOTE: buildPositions 는 dead code(실제 포지션은 BE /portfolio/summary 산출). 환율 미반영이라
    // native==KRW 로 둔다(타입 충족용). 통화 인지 값은 BE 응답을 쓴다.
    positions.push({
      key,
      ticker: pos.ticker,
      country: pos.country,
      currency: currencyForCountry(pos.country),
      assetName: pos.assetName,
      exchange: pos.exchange,
      holdingQuantity,
      avgBuyPrice,
      avgBuyPriceNative: avgBuyPrice,
      costBasis: pos.runningCost,
      costBasisNative: pos.runningCost,
      realizedPnL: 0,
      currentPrice: null,
      evaluation: null,
      evaluationNative: null,
      unrealizedPnL: null,
      lastNote: pos.lastNote,
      lastTradedAt: pos.lastTradedAt,
      accountIds: Array.from(pos.accountIds),
    });
  }

  return positions;
}

export function mergeQuotes(
  positions: Position[],
  quotes: QuoteMap,
  usdkrw: number | null = null,
): Position[] {
  // currentPrice 는 native(시세 그대로). 평가액은 현재 환율로 KRW(primary)+native 산출.
  // 원가(costBasis)는 거래 시점 환율로 KRW 고정 → 환산 불필요. 해외인데 환율 없으면 KRW 평가 null.
  return positions.map((pos) => {
    const quote = quotes[pos.key] ?? null;
    if (!quote) return pos;
    const evaluationNative = quote.price * pos.holdingQuantity;
    const evaluation = toKRW(evaluationNative, pos.currency, usdkrw);
    return {
      ...pos,
      currentPrice: quote.price,
      evaluation,
      evaluationNative,
      unrealizedPnL: evaluation === null ? null : evaluation - pos.costBasis,
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
      const key = `${ticker}:${trade.country_code ?? DEFAULT_COUNTRY_CODE}`;
      if (!posMap.has(key)) posMap.set(key, { qty: 0, costBasis: 0 });
      const p = posMap.get(key)!;
      if (trade.trade_type === TRADE_TYPE.BUY) {
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
      holdings: [],
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
    if (trade.trade_type === TRADE_TYPE.SELL) {
      totalRealizedPnL += pnlMap.get(trade.id) ?? 0;
    }
    const kst = toKST(new Date(trade.traded_at));
    if (kst.getFullYear() === thisYear && kst.getMonth() === thisMonth) {
      monthTradeCount++;
      if (trade.trade_type === TRADE_TYPE.SELL) {
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

// ── 시세 overlay (옵션 B) ──────────────────────────────────────────
// BE lite 응답(withQuotes=false)의 시세 비의존 값은 그대로 두고, FE 가 /stocks/quote 로
// 받은 시세를 derived 필드에만 덮어쓴다. trades 재순회(buildTotals/buildAccountSnapshots)
// 금지 — BE 계산값과의 불일치(sort_for_calc 패리티) 회피.

/**
 * totals 의 시세 의존 필드만 시세가 반영된 positions 로 재계산한다.
 * 시세 비의존 필드(totalRealizedPnL/totalCash/monthRealizedPnL/monthTradeCount)는
 * 인자 totals 의 BE 계산값을 그대로 유지한다.
 */
export function applyQuotesToTotals(
  totals: DashboardTotals,
  positionsWithQuotes: Position[],
): DashboardTotals {
  // evaluation/unrealized 는 mergeQuotes 가 이미 KRW(현재 환율 환산)로 채웠으므로 그대로 합산
  // (BE build_totals 와 동일). evaluation 이 null 인 포지션(시세/환율 미상)은 missing 으로 노출.
  let totalEvaluation = 0;
  let totalUnrealizedPnL = 0;
  const missingQuoteTickers: string[] = [];
  for (const p of positionsWithQuotes) {
    if (p.evaluation === null) {
      missingQuoteTickers.push(p.assetName);
      continue;
    }
    totalEvaluation += p.evaluation;
    if (p.unrealizedPnL !== null) totalUnrealizedPnL += p.unrealizedPnL;
  }

  return {
    ...totals,
    totalEvaluation,
    totalUnrealizedPnL,
    totalAssets: totalEvaluation + totals.totalCash,
    missingQuoteTickers,
  };
}

/**
 * 각 snapshot 의 stockEvaluation/totalValue 를 계좌별 holdings 수량 × 시세로 재계산한다.
 * 다계좌 동일 종목은 positions 합산 수량이 아니라 snapshot.holdings 의 계좌별 수량을 써야
 * 분배가 맞는다(BE build_account_snapshots 와 동일 규칙). 시세 없는 key 는 0.
 * account/cashBalance/holdings 는 그대로 유지.
 */
export function applyQuotesToSnapshots(
  snapshots: AccountSnapshot[],
  quotes: QuoteMap,
  usdkrw: number | null = null,
): AccountSnapshot[] {
  return snapshots.map((snapshot) => {
    let stockEvaluation = 0;
    // holdings 는 BE additive 필드라 구버전(미배포) BE 응답엔 없을 수 있다(버전 skew).
    // 가드 없이 순회하면 TypeError → 홈 렌더 크래시. 누락 시 빈 배열로 graceful degrade.
    for (const holding of snapshot.holdings ?? []) {
      const quote = quotes[holding.key] ?? null;
      if (!quote) continue;
      // native 평가액 → KRW 환산(계좌 현금은 KRW 가정). 환율 없는 US 는 제외.
      const currency = currencyForCountry(countryFromKey(holding.key));
      const krw = toKRW(quote.price * holding.quantity, currency, usdkrw);
      if (krw !== null) stockEvaluation += krw;
    }
    return {
      ...snapshot,
      stockEvaluation,
      totalValue: stockEvaluation + snapshot.cashBalance,
    };
  });
}

export interface AllocationEntry {
  name: string;
  value: number;
  color?: string;
}

/**
 * 종목별 자산 배분(도넛 입력). evaluation 은 mergeQuotes 가 이미 KRW 로 채웠으므로 그대로
 * 비중·정렬·총액에 쓴다(통화 일관). evaluation 이 null 인 포지션은 제외.
 * 상위 7종목 + 나머지 "기타" + 현금 "예수금".
 */
export function buildStockAllocation(
  positions: Position[],
  snapshots: AccountSnapshot[],
): AllocationEntry[] {
  const withEval = positions
    .map((p) => ({ p, krw: p.evaluation }))
    .filter((x): x is { p: Position; krw: number } => x.krw !== null && x.krw > 0);
  const cashTotal = snapshots.reduce((s, x) => s + x.cashBalance, 0);
  if (withEval.length === 0 && cashTotal === 0) return [];
  const sorted = [...withEval].sort((a, b) => b.krw - a.krw);
  const top = sorted.slice(0, 7);
  const rest = sorted.slice(7);
  const out: AllocationEntry[] = top.map(({ p, krw }) => ({ name: p.assetName, value: krw }));
  if (rest.length > 0) {
    out.push({ name: "기타", value: rest.reduce((s, x) => s + x.krw, 0) });
  }
  if (cashTotal > 0) {
    out.push({ name: "예수금", value: cashTotal, color: "var(--muted-foreground)" });
  }
  return out;
}
