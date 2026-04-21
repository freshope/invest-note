import type { MarketType } from "@/types/database";

const MARKET_LABELS: Record<string, string> = {
  STOCK: "주식",
  CRYPTO: "암호화폐",
  ETC: "기타",
};

interface TradeForDisplay {
  market_type: MarketType;
  country_code?: string | null;
  exchange?: string | null;
}

export function getCountryLabel(countryCode: string): string | null {
  if (countryCode === "KR") return "국내";
  if (countryCode === "US") return "해외";
  return null;
}

export function buildMarketDisplay(trade: TradeForDisplay): string {
  const countryCode = trade.country_code ?? "KR";
  const isStock = trade.market_type === "STOCK";
  const countryLabel = isStock ? getCountryLabel(countryCode) : null;
  return [
    MARKET_LABELS[trade.market_type] ?? trade.market_type,
    countryLabel,
    isStock ? trade.exchange : null,
  ]
    .filter(Boolean)
    .join("·");
}

export function getQuantityUnit(marketType: MarketType): string {
  if (marketType === "CRYPTO") return "개";
  if (marketType === "ETC") return "";
  return "주";
}
