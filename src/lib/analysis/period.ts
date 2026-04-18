import { subMonths, startOfYear, startOfDay } from "date-fns";
import { TZDate, tz } from "@date-fns/tz";

const KST = "Asia/Seoul";
const kstOpts = { in: tz(KST) };

export type Period = "1m" | "3m" | "6m" | "ytd" | "all";

export function parsePeriod(param: string | null): Period {
  if (param === "1m" || param === "3m" || param === "6m" || param === "ytd" || param === "all") {
    return param;
  }
  return "all";
}

function periodToRange(period: Period): { from: Date | null; to: Date } {
  const now = new TZDate(new Date(), KST);

  if (period === "all") return { from: null, to: now };

  if (period === "ytd") {
    return { from: startOfDay(startOfYear(now), kstOpts), to: now };
  }

  const months = period === "1m" ? 1 : period === "3m" ? 3 : 6;
  return { from: startOfDay(subMonths(now, months), kstOpts), to: now };
}

export function filterByPeriod<T extends { traded_at: string }>(trades: T[], period: Period): T[] {
  const { from, to } = periodToRange(period);
  const toTime = to.getTime();

  return trades.filter((t) => {
    const ts = new TZDate(new Date(t.traded_at), KST).getTime();
    if (from && ts < from.getTime()) return false;
    return ts <= toTime;
  });
}
