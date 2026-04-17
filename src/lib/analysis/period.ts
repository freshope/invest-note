import { toKST } from "@/lib/trade-utils";

export type Period = "1m" | "3m" | "6m" | "ytd" | "all";

export function parsePeriod(param: string | null): Period {
  if (param === "1m" || param === "3m" || param === "6m" || param === "ytd" || param === "all") {
    return param;
  }
  return "all";
}

export function periodToRange(period: Period): { from: Date | null; to: Date } {
  const now = toKST(new Date());

  if (period === "all") return { from: null, to: now };

  if (period === "ytd") {
    return { from: toKST(new Date(now.getFullYear(), 0, 1)), to: now };
  }

  const months = period === "1m" ? 1 : period === "3m" ? 3 : 6;
  const from = toKST(new Date(now.getFullYear(), now.getMonth() - months, now.getDate()));
  return { from, to: now };
}

export function filterByPeriod<T extends { traded_at: string }>(trades: T[], period: Period): T[] {
  const { from } = periodToRange(period);
  if (!from) return trades;
  const fromTime = from.getTime();
  return trades.filter((t) => toKST(new Date(t.traded_at)).getTime() >= fromTime);
}
