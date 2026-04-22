export function fmt(n: number): string {
  return n.toLocaleString("ko-KR");
}

/** Compact Korean number format: 억/만 for chart labels */
export function fmtCompact(n: number): string {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억`;
  if (n >= 10_000) return `${Math.round(n / 10_000)}만`;
  return n.toLocaleString("ko-KR");
}
