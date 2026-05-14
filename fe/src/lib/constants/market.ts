export const COUNTRY_CODES = ["KR", "US", "OTHER"] as const;
export type CountryCode = (typeof COUNTRY_CODES)[number];

export const COUNTRY_LABEL: Record<CountryCode, string> = {
  KR: "국내",
  US: "해외",
  OTHER: "기타",
};

export const DEFAULT_COUNTRY_CODE: CountryCode = "KR";

export function isCountryCode(value: string): value is CountryCode {
  return COUNTRY_CODES.includes(value as CountryCode);
}
