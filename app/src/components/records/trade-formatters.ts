import type { MarketType } from "@/types/database";
import { COUNTRY_LABEL, isCountryCode } from "@/lib/constants/market";

export const MARKET_LABELS: Record<MarketType, string> = {
  STOCK: "주식",
  CRYPTO: "암호화폐",
  ETC: "기타",
};

// OTHER는 fallback("기타") 처리 — 호출부 중 일부가 null 분기를 두고 있어 의미 보존
export function getCountryLabel(countryCode: string): string | null {
  if (!isCountryCode(countryCode)) return null;
  if (countryCode === "OTHER") return null;
  return COUNTRY_LABEL[countryCode];
}

export function getQuantityUnit(marketType: MarketType): string {
  if (marketType === "CRYPTO") return "개";
  if (marketType === "ETC") return "";
  return "주";
}
