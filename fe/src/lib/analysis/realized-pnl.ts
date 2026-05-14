import type { EmotionType, ReasoningTag, StrategyType, Trade } from "@/types/database";
import { TRADE_TYPE } from "@/lib/constants/trading";
import { DEFAULT_COUNTRY_CODE } from "@/lib/constants/market";

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
  holding_days: number | null;
  strategy_type: StrategyType | null;
  reasoning_tags: ReasoningTag[];
  emotion: EmotionType | null;
  matched_qty: number;
  running_qty_after: number;
};

export type ValidateMutationResult =
  | { ok: false; message: string }
  | { ok: true; affectedSellIds: string[]; newPnL: Map<string, number> };

export function groupKey(trade: Pick<Trade, "ticker_symbol" | "asset_name" | "country_code" | "account_id">): string {
  return `${trade.ticker_symbol ?? trade.asset_name}:${trade.country_code ?? DEFAULT_COUNTRY_CODE}:${trade.account_id}`;
}

export function tradeToGroupKey(trade: Pick<Trade, "ticker_symbol" | "asset_name" | "country_code" | "account_id">): TradeGroupKey {
  return {
    ticker: trade.ticker_symbol,
    assetName: trade.asset_name,
    country: trade.country_code ?? DEFAULT_COUNTRY_CODE,
    accountId: trade.account_id,
  };
}

// migration 006에서 모든 레코드의 ticker_symbol이 보장됨
function isSameGroup(trade: Trade, key: TradeGroupKey): boolean {
  if (trade.account_id !== key.accountId) return false;
  if ((trade.country_code ?? DEFAULT_COUNTRY_CODE) !== key.country) return false;
  const tradeTicker = trade.ticker_symbol ?? trade.asset_name;
  const targetTicker = key.ticker ?? key.assetName;
  return tradeTicker === targetTicker;
}

export function sortForCalc(trades: Trade[]): Trade[] {
  return [...trades].sort((a, b) => {
    const tDiff = new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime();
    if (tDiff !== 0) return tDiff;
    if (a.trade_type !== b.trade_type) return a.trade_type === TRADE_TYPE.BUY ? -1 : 1;
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });
}

// 항상 계산값 사용 — 수동 입력 불가
export function sellPnL(trade: Trade, avgCost: number, costQty?: number): number {
  const qty = costQty ?? trade.quantity;
  return trade.price * qty - avgCost * qty - trade.commission - trade.tax;
}

type ConsumedLot = {
  strategy: StrategyType | null;
  qty: number;
  order: number;
  timeMs: number;
  reasoningTags: ReasoningTag[];
  emotion: EmotionType | null;
};

function strategyFromConsumed(consumed: ConsumedLot[]): StrategyType | null {
  if (consumed.length === 0) return null;

  const byStrategy = new Map<StrategyType, { qty: number; order: number }>();
  for (const item of consumed) {
    const key = item.strategy ?? "UNKNOWN";
    const current = byStrategy.get(key) ?? { qty: 0, order: item.order };
    current.qty += item.qty;
    current.order = Math.min(current.order, item.order);
    byStrategy.set(key, current);
  }

  return Array.from(byStrategy.entries()).sort((a, b) => {
    const qtyDiff = b[1].qty - a[1].qty;
    return qtyDiff !== 0 ? qtyDiff : a[1].order - b[1].order;
  })[0][0];
}

// 가장 최근(timeMs 최대, 동률 시 order 최대) 소비 BUY의 tags/emotion
function metaFromConsumedLatest(
  consumed: ConsumedLot[],
): { tags: ReasoningTag[]; emotion: EmotionType | null } {
  if (consumed.length === 0) return { tags: [], emotion: null };
  let latest = consumed[0];
  for (const lot of consumed) {
    if (lot.timeMs > latest.timeMs || (lot.timeMs === latest.timeMs && lot.order > latest.order)) {
      latest = lot;
    }
  }
  return { tags: [...latest.reasoningTags], emotion: latest.emotion };
}

export function computeGroupPnL(
  trades: Trade[],
  key: TradeGroupKey,
): Map<string, GroupPnLEntry> {
  const result = new Map<string, GroupPnLEntry>();

  const group = sortForCalc(trades.filter((t) => isSameGroup(t, key)));

  let runningQty = 0;
  let runningCost = 0;
  const fifoLots: {
    qty: number;
    timeMs: number;
    strategy: StrategyType | null;
    reasoningTags: ReasoningTag[];
    emotion: EmotionType | null;
    order: number;
  }[] = [];
  let buyOrder = 0;

  for (const trade of group) {
    if (trade.trade_type === TRADE_TYPE.BUY) {
      runningQty += trade.quantity;
      runningCost += trade.price * trade.quantity;
      fifoLots.push({
        qty: trade.quantity,
        timeMs: new Date(trade.traded_at).getTime(),
        strategy: trade.strategy_type,
        reasoningTags: [...(trade.reasoning_tags ?? [])],
        emotion: trade.emotion,
        order: buyOrder,
      });
      buyOrder += 1;
    } else {
      const avgCost = runningQty > 0 ? runningCost / runningQty : 0;
      const matchedQty = Math.min(trade.quantity, runningQty);
      let remaining = trade.quantity;
      const sellTime = new Date(trade.traded_at).getTime();
      let weightedMs = 0;
      let totalConsumed = 0;
      const consumed: ConsumedLot[] = [];
      while (remaining > 0 && fifoLots.length > 0) {
        const slot = fifoLots[0];
        const consume = Math.min(slot.qty, remaining);
        weightedMs += (sellTime - slot.timeMs) * consume;
        totalConsumed += consume;
        consumed.push({
          strategy: slot.strategy,
          qty: consume,
          order: slot.order,
          timeMs: slot.timeMs,
          reasoningTags: slot.reasoningTags,
          emotion: slot.emotion,
        });
        slot.qty -= consume;
        remaining -= consume;
        if (slot.qty <= 0) fifoLots.shift();
      }
      const holdingDays =
        totalConsumed > 0 ? Math.floor(weightedMs / totalConsumed / (1000 * 60 * 60 * 24) + 0.5) : null;
      const meta = metaFromConsumedLatest(consumed);
      result.set(trade.id, {
        profit_loss: sellPnL(trade, avgCost, matchedQty),
        avg_buy_price: avgCost,
        holding_days: holdingDays,
        strategy_type: strategyFromConsumed(consumed),
        reasoning_tags: meta.tags,
        emotion: meta.emotion,
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
  const mutTrade = mutation.trade;
  const key = tradeToGroupKey(mutTrade);

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
    if (trade.trade_type === TRADE_TYPE.BUY) {
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

// 저장된 profit_loss 사용 — 정합성은 recalcGroupPnL이 보장
export function buildPnlMap(trades: Trade[]): Map<string, number> {
  const sells = trades.filter((t) => t.trade_type === TRADE_TYPE.SELL);
  return new Map(sells.map((t) => [t.id, Number(t.profit_loss ?? 0)]));
}

// 테스트/디버깅용 — 프로덕션 읽기 경로에서는 buildPnlMap(저장값)을 사용
export function computeRealizedPnL(trades: Trade[]): Map<string, number> {
  const result = new Map<string, number>();
  const sorted = sortForCalc(trades);
  const posMap = new Map<string, { runningQty: number; runningCost: number }>();

  for (const trade of sorted) {
    const key = groupKey(trade);
    if (!posMap.has(key)) posMap.set(key, { runningQty: 0, runningCost: 0 });
    const pos = posMap.get(key)!;

    if (trade.trade_type === TRADE_TYPE.BUY) {
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
