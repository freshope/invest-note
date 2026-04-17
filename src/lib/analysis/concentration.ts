import type { Trade } from "@/types/database";
import type { Position } from "@/lib/portfolio";

export const HHI_HIGH = 0.5;          // 집중 — 경고 수준
export const HHI_MID = 0.25;          // 보통
export const TOP1_WEIGHT_HIGH = 0.4;  // 단일 종목 비중 경고 임계치

export interface ConcentrationData {
  hhi: number;
  top3: { asset: string; weight: number }[];
  byCountry: { code: string; weight: number }[];
  byMarket: { type: string; weight: number }[];
}

export function computeConcentration(positions: Position[], trades: Trade[]): ConcentrationData {
  // evaluation이 없으면 costBasis로 fallback
  const values = positions.map((p) => ({
    key: p.key,
    asset: p.assetName,
    country: p.country,
    value: p.evaluation ?? p.costBasis,
  }));

  const total = values.reduce((s, v) => s + v.value, 0);

  if (total === 0) {
    return { hhi: 0, top3: [], byCountry: [], byMarket: [] };
  }

  // HHI: Σ(weight²)
  const hhi = values.reduce((s, v) => {
    const w = v.value / total;
    return s + w * w;
  }, 0);

  // top3
  const top3 = [...values]
    .sort((a, b) => b.value - a.value)
    .slice(0, 3)
    .map((v) => ({ asset: v.asset, weight: v.value / total }));

  // byCountry
  const countryMap = new Map<string, number>();
  for (const v of values) {
    countryMap.set(v.country, (countryMap.get(v.country) ?? 0) + v.value);
  }
  const byCountry = Array.from(countryMap.entries())
    .map(([code, val]) => ({ code, weight: val / total }))
    .sort((a, b) => b.weight - a.weight);

  // byMarket: trades에서 종목별 market_type 추출 (가장 최근 BUY 기준)
  const marketByKey = new Map<string, string>();
  for (const t of trades
    .filter((t) => t.trade_type === "BUY")
    .sort((a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime())) {
    const key = `${t.ticker_symbol ?? t.asset_name}:${t.country_code ?? "KR"}`;
    marketByKey.set(key, t.market_type);
  }

  const marketMap = new Map<string, number>();
  for (const v of values) {
    const mt = marketByKey.get(v.key) ?? "ETC";
    marketMap.set(mt, (marketMap.get(mt) ?? 0) + v.value);
  }
  const byMarket = Array.from(marketMap.entries())
    .map(([type, val]) => ({ type, weight: val / total }))
    .sort((a, b) => b.weight - a.weight);

  return { hhi, top3, byCountry, byMarket };
}
