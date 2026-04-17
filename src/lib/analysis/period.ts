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
    // Date.UTC를 사용해 KST 자정을 "toKST 공간"에서 직접 표현
    // (toKST로 감싸면 +9h가 이중 적용돼 실효 경계가 KST 09:00이 됨)
    return { from: new Date(Date.UTC(now.getFullYear(), 0, 1)), to: now };
  }

  const months = period === "1m" ? 1 : period === "3m" ? 3 : 6;
  const targetMonth = now.getMonth() - months;
  const targetYear = now.getFullYear();
  // Clamp day to avoid month-end overflow (e.g. Mar 31 - 1m → Feb 28, not Mar 3)
  const daysInTargetMonth = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();
  const clampedDay = Math.min(now.getDate(), daysInTargetMonth);
  const from = new Date(Date.UTC(targetYear, targetMonth, clampedDay));
  return { from, to: now };
}

export function filterByPeriod<T extends { traded_at: string }>(trades: T[], period: Period): T[] {
  const { from, to } = periodToRange(period);
  const toTime = to.getTime();
  if (!from) return trades.filter((t) => toKST(new Date(t.traded_at)).getTime() <= toTime);
  const fromTime = from.getTime();
  return trades.filter((t) => {
    const ts = toKST(new Date(t.traded_at)).getTime();
    return ts >= fromTime && ts <= toTime;
  });
}
