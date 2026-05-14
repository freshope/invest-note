import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { TZDate } from "@date-fns/tz";
import type { Trade, Account } from "@/types/database";
import { KST } from "@/lib/constants/time";

export type TradeWithAccount = Trade & { account?: Pick<Account, "name" | "broker"> };

export function toKST(utcDate: Date): Date {
  return new TZDate(utcDate, KST);
}

export function groupByDate(trades: TradeWithAccount[]): [string, TradeWithAccount[]][] {
  // 백엔드 정렬에 의존하지 않고 traded_at desc 로 정렬한 뒤 그룹화한다.
  // Map insertion order 가 그대로 그룹 출현 순서이므로 사전 정렬이 곧 화면 순서를 결정한다.
  const sorted = [...trades].sort(
    (a, b) => new Date(b.traded_at).getTime() - new Date(a.traded_at).getTime(),
  );
  const map = new Map<string, TradeWithAccount[]>();
  for (const trade of sorted) {
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

export function formatTradedAtLabel(input: Date | string): string {
  const date = typeof input === "string" ? new Date(input) : input;
  return format(date, "yyyy년 M월 d일 (EEE)", { locale: ko });
}
