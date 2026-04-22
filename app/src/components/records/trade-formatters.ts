import type { MarketType } from "@/types/database";

export const MARKET_LABELS: Record<MarketType, string> = {
  STOCK: "주식",
  CRYPTO: "암호화폐",
  ETC: "기타",
};

export function getCountryLabel(countryCode: string): string | null {
  if (countryCode === "KR") return "국내";
  if (countryCode === "US") return "해외";
  return null;
}

export function getQuantityUnit(marketType: MarketType): string {
  if (marketType === "CRYPTO") return "개";
  if (marketType === "ETC") return "";
  return "주";
}
