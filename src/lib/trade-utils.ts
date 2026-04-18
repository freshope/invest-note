import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { TZDate } from "@date-fns/tz";
import type { Trade, Account } from "@/types/database";

const KST = "Asia/Seoul";

export type TradeWithAccount = Trade & { account?: Pick<Account, "name" | "broker"> };

export function toKST(utcDate: Date): Date {
  return new TZDate(utcDate, KST);
}

export function groupByDate(trades: TradeWithAccount[]): [string, TradeWithAccount[]][] {
  const map = new Map<string, TradeWithAccount[]>();
  for (const trade of trades) {
    const kst = new TZDate(new Date(trade.traded_at), KST);
    const key = format(kst, "yyyy-MM-dd");
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(trade);
  }
  return Array.from(map.entries());
}

export function formatDateLabel(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return format(date, "yyyy년 M월 d일 (EEE)", { locale: ko });
}
