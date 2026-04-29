import { PNL_COLORS } from "./constants/colors";

export function fmt(n: number): string {
  return n.toLocaleString("ko-KR");
}

export function formatPnL(value: number): string {
  const rounded = Math.round(value);
  if (rounded === 0) return "0원";
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${fmt(rounded)}원`;
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
