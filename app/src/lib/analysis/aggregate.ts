import type { Trade, ReasoningTag } from "@/types/database";
import type { Period } from "./period";

export interface StrategyStats {
  type: string;
  count: number;
  resultCount: number;  // result 입력된 SELL 수 — winRate 신뢰도 판단용
  winRate: number;
  avgPnL: number;
  avgHoldingDays: number;
}

export interface EmotionStats {
  type: string;
  count: number;        // BUY + SELL 전체 빈도 (감정 노출 빈도)
  sellCount: number;    // SELL만 (winRate 분모 — 실제 결과 판단 기준)
  resultCount: number;  // result 입력된 SELL 수 — winRate 신뢰도 판단용
  winRate: number;
  avgPnL: number;
}

export interface TagStats {
  tag: string;
  count: number;
  winRate: number;
  avgPnL: number;
}

export interface AnalysisSummary {
  period?: Period;
  totalTrades: number;
  sellTrades: number;
  winRate: number;
  totalProfitLoss: number;
  byStrategy: StrategyStats[];
  byEmotion: EmotionStats[];
  byTag: TagStats[];
  missingTagRate: number;
  feelingRate: number;
  reflectionRate: number;
  resultInputRate: number;
}

// pnlMap, holdingDaysMap: allTrades 기준으로 WAC/FIFO 정확도 보장
// allTrades: byTag 태그 귀속 시 기간 이전 BUY 포함을 위해 필요 (없으면 trades 내 BUY만 사용)
export function computeSummary(
  trades: Trade[],
  pnlMap: Map<string, number>,
  holdingDaysMap: Map<string, number>,
  allTrades?: Trade[],
): AnalysisSummary {
  const sells = trades.filter((t) => t.trade_type === "SELL");
  const buys = trades.filter((t) => t.trade_type === "BUY");

  const totalTrades = trades.length;
  const sellTrades = sells.length;

  const sellsWithResult = sells.filter((t) => t.result != null);
  const winCount = sellsWithResult.filter((t) => t.result === "SUCCESS").length;
  const winRate = sellsWithResult.length > 0 ? (winCount / sellsWithResult.length) * 100 : 0;

  const totalProfitLoss = sells.reduce((sum, t) => sum + (pnlMap.get(t.id) ?? 0), 0);

  // --- byStrategy ---
  const stratMap = new Map<string, { pnls: number[]; results: string[]; days: number[] }>();
  for (const t of sells) {
    const key = t.strategy_type ?? "UNKNOWN";
    if (!stratMap.has(key)) stratMap.set(key, { pnls: [], results: [], days: [] });
    const s = stratMap.get(key)!;
    s.pnls.push(pnlMap.get(t.id) ?? 0);
    if (t.result) s.results.push(t.result);
    const hd = holdingDaysMap.get(t.id);
    if (hd != null) s.days.push(hd);
  }

  const byStrategy: StrategyStats[] = Array.from(stratMap.entries())
    .map(([type, s]) => ({
      type,
      count: s.pnls.length,
      resultCount: s.results.length,
      winRate:
        s.results.length > 0
          ? (s.results.filter((r) => r === "SUCCESS").length / s.results.length) * 100
          : 0,
      avgPnL: s.pnls.length > 0 ? s.pnls.reduce((a, b) => a + b, 0) / s.pnls.length : 0,
      avgHoldingDays:
        s.days.length > 0 ? s.days.reduce((a, b) => a + b, 0) / s.days.length : 0,
    }))
    .sort((a, b) => b.count - a.count);

  // --- byEmotion ---
  // count: BUY+SELL 전체 감정 노출 빈도
  // sellCount: SELL만 (winRate/avgPnL 분모)
  const emotionMap = new Map<
    string,
    { totalCount: number; sellCount: number; pnls: number[]; results: string[] }
  >();
  for (const t of trades) {
    if (!t.emotion) continue;
    if (!emotionMap.has(t.emotion))
      emotionMap.set(t.emotion, { totalCount: 0, sellCount: 0, pnls: [], results: [] });
    const e = emotionMap.get(t.emotion)!;
    e.totalCount++;
    if (t.trade_type === "SELL") {
      e.sellCount++;
      e.pnls.push(pnlMap.get(t.id) ?? 0);
      if (t.result) e.results.push(t.result);
    }
  }

  const byEmotion: EmotionStats[] = Array.from(emotionMap.entries())
    .map(([type, e]) => ({
      type,
      count: e.totalCount,
      sellCount: e.sellCount,
      resultCount: e.results.length,
      winRate:
        e.results.length > 0
          ? (e.results.filter((r) => r === "SUCCESS").length / e.results.length) * 100
          : 0,
      avgPnL: e.pnls.length > 0 ? e.pnls.reduce((a, b) => a + b, 0) / e.pnls.length : 0,
    }))
    .sort((a, b) => b.count - a.count);

  // --- byTag ---
  // 기간 이전 BUY 태그도 포함해야 정확 — allTrades 제공 시 전체 BUY 사용
  const allBuys = allTrades ? allTrades.filter((t) => t.trade_type === "BUY") : buys;
  const buysByKey = new Map<string, Trade[]>();
  for (const t of [...allBuys].sort(
    (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
  )) {
    const key = `${t.ticker_symbol ?? t.asset_name}:${t.country_code ?? "KR"}`;
    if (!buysByKey.has(key)) buysByKey.set(key, []);
    buysByKey.get(key)!.push(t);
  }

  const tagMap = new Map<string, { pnls: number[]; results: string[] }>();
  for (const sell of sells) {
    const key = `${sell.ticker_symbol ?? sell.asset_name}:${sell.country_code ?? "KR"}`;
    const buysForKey = buysByKey.get(key) ?? [];
    const sellTime = new Date(sell.traded_at).getTime();
    const prevBuys = buysForKey.filter((b) => new Date(b.traded_at).getTime() <= sellTime);
    const tags: ReasoningTag[] = prevBuys.at(-1)?.reasoning_tags ?? [];
    if (tags.length === 0) continue;

    for (const tag of tags) {
      if (!tagMap.has(tag)) tagMap.set(tag, { pnls: [], results: [] });
      const tm = tagMap.get(tag)!;
      tm.pnls.push(pnlMap.get(sell.id) ?? 0);
      if (sell.result) tm.results.push(sell.result);
    }
  }

  const byTag: TagStats[] = Array.from(tagMap.entries())
    .map(([tag, tm]) => ({
      tag,
      count: tm.pnls.length,
      winRate:
        tm.results.length > 0
          ? (tm.results.filter((r) => r === "SUCCESS").length / tm.results.length) * 100
          : 0,
      avgPnL: tm.pnls.length > 0 ? tm.pnls.reduce((a, b) => a + b, 0) / tm.pnls.length : 0,
    }))
    .sort((a, b) => b.count - a.count);

  // --- 메타 지표 ---
  const missingTagRate =
    buys.length > 0
      ? (buys.filter((t) => t.reasoning_tags.length === 0).length / buys.length) * 100
      : 0;
  const feelingRate =
    buys.length > 0
      ? (buys.filter((t) => t.reasoning_tags.includes("FEELING")).length / buys.length) * 100
      : 0;
  const reflectionRate =
    sells.length > 0
      ? (sells.filter((t) => t.reflection_note != null && t.reflection_note.trim() !== "")
          .length /
          sells.length) *
        100
      : 0;
  const resultInputRate =
    sells.length > 0 ? (sellsWithResult.length / sells.length) * 100 : 0;

  return {
    totalTrades,
    sellTrades,
    winRate,
    totalProfitLoss,
    byStrategy,
    byEmotion,
    byTag,
    missingTagRate,
    feelingRate,
    reflectionRate,
    resultInputRate,
  };
}
