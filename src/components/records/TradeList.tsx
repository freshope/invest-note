"use client";

import { useState, useCallback } from "react";
import { TradeCard } from "./TradeCard";
import { TradeFormPanel } from "./TradeFormPanel";
import { TradeDetailPanel } from "./TradeDetailPanel";
import { CsvUploadButton } from "./CsvUploadButton";
import { groupByDate, formatDateLabel, type TradeWithAccount } from "@/lib/trade-utils";
import type { Account } from "@/types/database";
import { PlusIcon } from "lucide-react";

interface TradeListProps {
  trades: TradeWithAccount[];
  accounts: Account[];
}


export function TradeList({ trades, accounts }: TradeListProps) {
  const [formOpen, setFormOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<TradeWithAccount | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const grouped = groupByDate(trades);

  const handleDetailClose = useCallback((open: boolean) => {
    setDetailOpen(open);
    if (!open) setSelectedTrade(null);
  }, []);

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
                    <TradeCard
                      key={trade.id}
                      trade={trade}
                      onPress={() => {
                        setSelectedTrade(trade);
                        setDetailOpen(true);
                      }}
                    />
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

      {/* 거래 상세 패널 */}
      {detailOpen && selectedTrade && (
        <TradeDetailPanel
          open={detailOpen}
          onOpenChange={handleDetailClose}
          trade={selectedTrade}
          accounts={accounts}
          allTrades={trades}
        />
      )}
    </>
  );
}
