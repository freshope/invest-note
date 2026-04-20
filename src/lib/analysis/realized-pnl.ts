import type { Trade } from "@/types/database";

export type TradeGroupKey = {
  ticker: string | null;
  assetName: string;
  country: string;
  accountId: string;
};

export type MutationType = "insert" | "update" | "delete";

export type Mutation =
  | { type: "insert"; trade: Trade }
  | { type: "update"; trade: Trade; patch: Partial<Trade> }
  | { type: "delete"; trade: Trade };

export type GroupPnLEntry = {
  profit_loss: number;
  avg_buy_price: number;
  matched_qty: number;
  running_qty_after: number;
};

export type ValidateMutationResult =
  | { ok: false; message: string }
  | { ok: true; affectedSellIds: string[]; newPnL: Map<string, number> };

// (종목+국가+계좌) 그룹 키 문자열
export function groupKey(trade: Pick<Trade, "ticker_symbol" | "asset_name" | "country_code" | "account_id">): string {
  return `${trade.ticker_symbol ?? trade.asset_name}:${trade.country_code ?? "KR"}:${trade.account_id}`;
}

// 그룹 매칭 — ticker_symbol(없으면 asset_name) 기준 단일 비교
// migration 006에서 모든 레코드의 ticker_symbol이 보장됨
function isSameGroup(trade: Trade, key: TradeGroupKey): boolean {
  if (trade.account_id !== key.accountId) return false;
  if ((trade.country_code ?? "KR") !== key.country) return false;
  const tradeTicker = trade.ticker_symbol ?? trade.asset_name;
  const targetTicker = key.ticker ?? key.assetName;
  return tradeTicker === targetTicker;
}

// 계산용 정렬: traded_at asc → 같은 날이면 BUY 먼저 → created_at asc
export function sortForCalc(trades: Trade[]): Trade[] {
  return [...trades].sort((a, b) => {
    const tDiff = new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime();
    if (tDiff !== 0) return tDiff;
    if (a.trade_type !== b.trade_type) return a.trade_type === "BUY" ? -1 : 1;
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });
}

// WAC 기반 SELL 손익 계산 (항상 계산값 사용 — 수동 입력 불가)
export function sellPnL(trade: Trade, avgCost: number, costQty?: number): number {
  const qty = costQty ?? trade.quantity;
  return trade.price * qty - avgCost * qty - trade.commission - trade.tax;
}

// 특정 그룹의 SELL별 profit_loss 계산 — Map<sellId, GroupPnLEntry>
export function computeGroupPnL(
  trades: Trade[],
  key: TradeGroupKey,
): Map<string, GroupPnLEntry> {
  const result = new Map<string, GroupPnLEntry>();

  const group = sortForCalc(trades.filter((t) => isSameGroup(t, key)));

  let runningQty = 0;
  let runningCost = 0;

  for (const trade of group) {
    if (trade.trade_type === "BUY") {
      runningQty += trade.quantity;
      runningCost += trade.price * trade.quantity;
    } else {
      const avgCost = runningQty > 0 ? runningCost / runningQty : 0;
      const matchedQty = Math.min(trade.quantity, runningQty);
      result.set(trade.id, {
        profit_loss: sellPnL(trade, avgCost, matchedQty),
        avg_buy_price: avgCost,
        matched_qty: matchedQty,
        running_qty_after: Math.max(0, runningQty - trade.quantity),
      });
      runningCost = Math.max(0, runningCost - avgCost * matchedQty);
      runningQty = Math.max(0, runningQty - trade.quantity);
    }
  }

  return result;
}

// 수정/삭제/삽입 가상 적용 후 oversell 여부 검증
export function validateMutation(trades: Trade[], mutation: Mutation): ValidateMutationResult {
  let virtual: Trade[];
  const mutTrade = mutation.type === "update" ? mutation.trade : mutation.trade;
  const key: TradeGroupKey = {
    ticker: mutTrade.ticker_symbol,
    assetName: mutTrade.asset_name,
    country: mutTrade.country_code ?? "KR",
    accountId: mutTrade.account_id,
  };

  if (mutation.type === "insert") {
    virtual = [...trades, mutation.trade];
  } else if (mutation.type === "update") {
    const patched = { ...mutation.trade, ...mutation.patch };
    virtual = trades.map((t) => (t.id === mutation.trade.id ? patched : t));
  } else {
    virtual = trades.filter((t) => t.id !== mutation.trade.id);
  }

  const group = sortForCalc(virtual.filter((t) => isSameGroup(t, key)));

  let runningQty = 0;
  let runningCost = 0;
  const affectedSellIds: string[] = [];
  const newPnL = new Map<string, number>();

  for (const trade of group) {
    if (trade.trade_type === "BUY") {
      runningQty += trade.quantity;
      runningCost += trade.price * trade.quantity;
    } else {
      if (runningQty <= 0) {
        return { ok: false, message: "보유 수량이 없어 매도할 수 없습니다." };
      }
      if (trade.quantity > runningQty) {
        return { ok: false, message: "보유 수량이 부족한 매도 거래가 생깁니다." };
      }
      const avgCost = runningCost / runningQty;
      const matchedQty = Math.min(trade.quantity, runningQty);
      const pnl = sellPnL(trade, avgCost, matchedQty);
      affectedSellIds.push(trade.id);
      newPnL.set(trade.id, pnl);
      runningCost = Math.max(0, runningCost - avgCost * matchedQty);
      runningQty = Math.max(0, runningQty - trade.quantity);
    }
  }

  return { ok: true, affectedSellIds, newPnL };
}

// SELL 거래의 P&L 반환 — 저장값 우선, null이면 fallbackMap 조회 (백필 전 호환)
export function getPnL(trade: Trade, fallbackMap?: Map<string, number>): number {
  if (trade.profit_loss != null) return Number(trade.profit_loss);
  return fallbackMap?.get(trade.id) ?? 0;
}

// 저장된 profit_loss 우선 pnlMap 생성 (분석/집계 전달용)
// null인 거래는 WAC fallback으로 채움 (백필 완료 후에는 항상 저장값 사용)
export function buildPnlMap(trades: Trade[]): Map<string, number> {
  const fallback = computeRealizedPnL(trades);
  const result = new Map<string, number>();
  for (const t of trades) {
    if (t.trade_type === "SELL") {
      result.set(t.id, t.profit_loss != null ? Number(t.profit_loss) : (fallback.get(t.id) ?? 0));
    }
  }
  return result;
}

// 전체 거래에서 각 SELL trade.id → 실현손익 (fallback 경로용)
export function computeRealizedPnL(trades: Trade[]): Map<string, number> {
  const result = new Map<string, number>();
  const sorted = sortForCalc(trades);
  const posMap = new Map<string, { runningQty: number; runningCost: number }>();

  for (const trade of sorted) {
    const key = groupKey(trade);
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
