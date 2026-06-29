import type { MarketType } from "@/types/database";
import { COUNTRY_LABEL, isCountryCode } from "@/lib/constants/market";
export { MARKET_LABELS } from "@/lib/constants/trading";

// OTHER는 fallback("기타") 처리 — 호출부 중 일부가 null 분기를 두고 있어 의미 보존
export function getCountryLabel(countryCode: string): string | null {
  if (!isCountryCode(countryCode)) return null;
  if (countryCode === "OTHER") return null;
  return COUNTRY_LABEL[countryCode];
}

// 거래 표시명 — 한글명(name_ko) 우선, 없으면 영문/원본 asset_name fallback.
// US 종목은 asset_name 이 영문(예 "Apple Inc.")이고 name_ko 에 "애플" 이 채워진다.
// name_ko 미보유(롱테일 US/KR)는 asset_name 그대로. 표시 전용 — 계산/매칭 키는 asset_name 유지.
export function tradeDisplayName(trade: { asset_name: string; name_ko?: string | null }): string {
  // `||` (not `??`): null/undefined 뿐 아니라 빈 문자열 name_ko 도 asset_name 으로 fallback.
  return trade.name_ko || trade.asset_name;
}

export function getQuantityUnit(marketType: MarketType): string {
  if (marketType === "CRYPTO") return "개";
  if (marketType === "ETC") return "";
  return "주";
}
