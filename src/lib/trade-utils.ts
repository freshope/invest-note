import { format } from "date-fns";
import { ko } from "date-fns/locale";
import type { Trade, Account } from "@/types/database";

export type TradeWithAccount = Trade & { account?: Pick<Account, "name" | "broker"> };

// UTC 타임스탬프를 KST(UTC+9) 기준 Date로 변환
export function toKST(utcDate: Date): Date {
  return new Date(utcDate.getTime() + 9 * 60 * 60 * 1000);
}

// 날짜별 그룹핑 — KST 기준 날짜 키 사용
// toKST는 UTC ms에 +9h를 더한 Date를 반환하므로, 브라우저 로컬 타임존과 무관하게
// ISO 문자열의 날짜 부분(UTC+9 기준)을 직접 사용해야 이중 오프셋을 방지한다.
export function groupByDate(trades: TradeWithAccount[]): [string, TradeWithAccount[]][] {
  const map = new Map<string, TradeWithAccount[]>();
  for (const trade of trades) {
    const key = toKST(new Date(trade.traded_at)).toISOString().slice(0, 10);
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
