import { PNL_COLORS } from "./constants/colors";

export function fmt(n: number): string {
  return n.toLocaleString("ko-KR");
}

/** part/total 백분율(정수). total<=0이면 0. */
export function calcPercent(part: number, total: number): number {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

/** (current - prev) / prev 백분율, 소수점 2자리. prev<=0이면 0. */
export function calcChangePercent(current: number, prev: number): number {
  return prev > 0 ? Math.round(((current - prev) / prev) * 10000) / 100 : 0;
}

export function formatPnL(value: number): string {
  const rounded = Math.round(value);
  if (rounded === 0) return "0원";
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${fmt(rounded)}원`;
}

// ─────────────────────────── 통화 인지 포맷 (해외주식 Phase A — 준비) ───────────────────────────
// 기존 formatPnL/fmt 는 KRW("원") 고정으로 유지(호출부 무변경). 통화 분기가 필요한 화면은
// 아래 통화 인지 유틸을 쓴다. 실제 와이어링은 통화 인지 합산이 들어오는 Phase B 에서.

export const CURRENCY_SYMBOL: Record<string, string> = { KRW: "₩", USD: "$" };

/** country_code → 거래 통화. KR=KRW, US=USD, 그 외는 KRW fallback. */
export function currencyForCountry(country: string): "KRW" | "USD" {
  return country === "US" ? "USD" : "KRW";
}

/** 통화 기호. 미등록 통화는 통화 코드 그대로 반환. */
export function currencySymbol(currency: string): string {
  return CURRENCY_SYMBOL[currency] ?? currency;
}

/**
 * native 통화 금액을 KRW 로 환산. KRW 는 그대로, USD 는 ×usdkrw.
 * 환산 불가(USD 인데 환율 null, 또는 미지원 통화)면 null — 호출측이 missing 처리해
 * 조용한 통화 혼재 합산을 막는다(BE domain.to_krw 와 동일 규칙).
 */
export function toKRW(value: number, currency: string, usdkrw: number | null): number | null {
  if (currency === "KRW") return value;
  if (currency === "USD") return usdkrw != null ? value * usdkrw : null;
  return null;
}

/**
 * 통화별 금액 포맷. KRW 는 정수 + "원"(한국 관행), 그 외는 기호 접두 + 소수 2자리.
 * 예: formatMoney(1234,"KRW")="1,234원", formatMoney(12.5,"USD")="$12.50".
 */
export function formatMoney(value: number, currency: string = "KRW"): string {
  const decimals = currency === "KRW" ? 0 : 2;
  const n = value.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return currency === "KRW" ? `${n}원` : `${currencySymbol(currency)}${n}`;
}

/** 환율 표시 포맷. ₩ 접두 + 소수 2자리. 예: formatFxRate(1350)="₩1,350.00". */
export function formatFxRate(rate: number): string {
  return `₩${rate.toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * ISO 시각 → 한국시각(KST) "HH:mm". timeZone 고정으로 디바이스/CI TZ 무관하게 KST 기준 표시.
 * 잘못된 입력이면 null.
 */
export function formatTimeKST(iso: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("ko-KR", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    minute: "2-digit",
    // hour12:false 는 ICU 버전에 따라 h23/h24 로 갈려 자정이 "24:00" 으로 나올 수 있다.
    // h23 으로 고정해 00–23 범위(자정 = "00:00")를 보장한다.
    hourCycle: "h23",
  });
}

/** 통화별 손익 포맷(부호 포함). 0은 부호 없이. 음수는 기호 앞에 '-'. */
export function formatPnLCurrency(value: number, currency: string = "KRW"): string {
  const decimals = currency === "KRW" ? 0 : 2;
  const rounded = currency === "KRW" ? Math.round(value) : Number(value.toFixed(decimals));
  if (rounded === 0) return formatMoney(0, currency);
  const sign = rounded > 0 ? "+" : "-";
  return `${sign}${formatMoney(Math.abs(rounded), currency)}`;
}

/** 부호 + 소수점 + % 표시. 0은 부호 없이, -0 케이스는 0으로 정규화. */
export function formatPctSigned(n: number, decimals: number = 2): string {
  const rounded = Number(n.toFixed(decimals));
  if (rounded === 0) return `${(0).toFixed(decimals)}%`;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded.toFixed(decimals)}%`;
}

/** Compact Korean number format: 억/만 for chart labels */
export function fmtCompact(n: number): string {
  if (n >= 100_000_000) return `${(n / 100_000_000).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}억`;
  if (n >= 10_000) return `${Math.round(n / 10_000).toLocaleString("ko-KR")}만`;
  return n.toLocaleString("ko-KR");
}

/** Form number input display: returns comma-formatted string for positive numbers, "" otherwise */
export function fmtNumberInput(n: number | null | undefined): string {
  return n != null && n > 0 ? n.toLocaleString("ko-KR") : "";
}

/** Strips non-numeric characters (except decimal point) and re-formats with thousand separators */
export function formatNumberInput(raw: string): string {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const parts = cleaned.split(".");
  const integer = parts[0] || "";
  const decimal = parts.length > 1 ? "." + parts[1] : "";
  if (!integer && !decimal) return "";
  return (integer ? Number(integer).toLocaleString("ko-KR") : "") + decimal;
}

/** Parses a user input string to a number — strips all non-numeric chars except decimal point */
export function parseNumberInput(s: string): number {
  return Number(s.replace(/[^0-9.]/g, "")) || 0;
}

export type SignFallback = "foreground" | "muted" | "none";

/**
 * 손익/등락 색상 클래스. 0일 때 fallback으로 분기 — "none"은 부모 색 상속용 빈 문자열.
 * 빈 문자열을 자동으로 무시하는 `cn()` 안에서 사용.
 */
export function signColor(value: number, fallback: SignFallback = "foreground"): string {
  if (value > 0) return PNL_COLORS.rise.text;
  if (value < 0) return PNL_COLORS.fall.text;
  if (fallback === "muted") return "text-muted-foreground";
  if (fallback === "none") return "";
  return "text-foreground";
}
