export function fmt(n: number): string {
  return n.toLocaleString("ko-KR");
}

/** Compact Korean number format: 억/만 for chart labels */
export function fmtCompact(n: number): string {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억`;
  if (n >= 10_000) return `${Math.round(n / 10_000)}만`;
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
