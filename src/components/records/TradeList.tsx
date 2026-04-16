"use client";

import { useState } from "react";
import { Button } from "@/components/base/Button";
import { TradeCard } from "./TradeCard";
import { TradeFormPanel } from "./TradeFormPanel";
import { CsvUploadButton } from "./CsvUploadButton";
import type { Trade, Account } from "@/types/database";
import { PlusIcon } from "lucide-react";
import { format } from "date-fns";
import { ko } from "date-fns/locale";

type TradeWithAccount = Trade & { account?: Pick<Account, "name" | "broker"> };

interface TradeListProps {
  trades: TradeWithAccount[];
  accounts: Account[];
}

// UTC 타임스탬프를 KST(UTC+9) 기준 Date로 변환
function toKST(utcDate: Date): Date {
  return new Date(utcDate.getTime() + 9 * 60 * 60 * 1000);
}

// 날짜별 그룹핑 — KST 기준 날짜 키 사용
function groupByDate(trades: TradeWithAccount[]): [string, TradeWithAccount[]][] {
  const map = new Map<string, TradeWithAccount[]>();
  for (const trade of trades) {
    const key = format(toKST(new Date(trade.traded_at)), "yyyy-MM-dd");
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(trade);
  }
  return Array.from(map.entries());
}

function formatDateLabel(dateStr: string): string {
  // dateStr은 "yyyy-MM-dd" 형식의 KST 날짜 키
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d); // 로컬 날짜 생성 (타임존 영향 없음)
  return format(date, "yyyy년 M월 d일 (EEE)", { locale: ko });
}

export function TradeList({ trades, accounts }: TradeListProps) {
  const [formOpen, setFormOpen] = useState(false);
  const grouped = groupByDate(trades);

  return (
    <>
      {/* 헤더 */}
      <div className="sticky top-0 z-10 bg-background px-5 pt-6 pb-3 flex items-center justify-between">
        <h1 className="text-[20px] font-bold text-foreground">기록</h1>
        <CsvUploadButton />
      </div>

      {/* 목록 */}
      <div className="px-5 pb-6">
        {trades.length === 0 ? (
          <div className="rounded-2xl bg-muted/60 p-8 text-center space-y-4 mt-2">
            <p className="text-[15px] font-semibold text-foreground">거래 기록이 없어요</p>
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              우측 하단 버튼을 눌러<br />첫 거래를 기록해보세요
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {grouped.map(([dateKey, dayTrades]) => (
              <div key={dateKey}>
                <p className="text-[13px] font-semibold text-muted-foreground mb-2">
                  {formatDateLabel(dateKey)}
                </p>
                <div className="space-y-2">
                  {dayTrades.map((trade) => (
                    <TradeCard key={trade.id} trade={trade} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* FAB */}
      <button
        type="button"
        onClick={() => setFormOpen(true)}
        className="fixed bottom-28 right-5 z-20 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg active:scale-95 transition-transform"
        aria-label="거래 등록"
      >
        <PlusIcon className="h-6 w-6" strokeWidth={2.5} />
      </button>

      {/* 거래 등록 패널 */}
      {formOpen && (
        <TradeFormPanel
          open={formOpen}
          onOpenChange={setFormOpen}
          accounts={accounts}
        />
      )}
    </>
  );
}
