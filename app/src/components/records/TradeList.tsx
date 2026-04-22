"use client";

import { useState, useMemo, useEffect } from "react";
import { TradeCard } from "./TradeCard";
import { TradeFormPanel } from "./TradeFormPanel";
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import { CsvUploadButton } from "./CsvUploadButton";
import { AccountFilter } from "./AccountFilter";
import { groupByDate, formatDateLabel, type TradeWithAccount } from "@/lib/trade-utils";
import type { Account } from "@/types/database";
import { PlusIcon } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";

interface TradeListProps {
  trades: TradeWithAccount[];
  accounts: Account[];
}

export function TradeList({ trades, accounts }: TradeListProps) {
  const [formOpen, setFormOpen] = useState(false);
  const [selectedAccountId, setSelectedAccountId] = useState("all");
  const { openTrade } = useDetailPanel();

  useEffect(() => {
    if (selectedAccountId === "all") return;
    if (!accounts.some((a) => a.id === selectedAccountId)) {
      setSelectedAccountId("all");
    }
  }, [accounts]);

  const filteredTrades = useMemo(
    () =>
      selectedAccountId === "all"
        ? trades
        : trades.filter((t) => t.account_id === selectedAccountId),
    [trades, selectedAccountId],
  );

  const grouped = useMemo(() => groupByDate(filteredTrades), [filteredTrades]);

  return (
    <>
      <div className="sticky top-0 z-10 bg-background">
        <PageHeader title="기록" actions={<CsvUploadButton />} sticky={false} />
        {accounts.length >= 2 && (
          <AccountFilter
            accounts={accounts}
            value={selectedAccountId}
            onChange={setSelectedAccountId}
          />
        )}
      </div>

      <div className="px-5 pb-6">
        {trades.length === 0 ? (
          <div className="rounded-2xl bg-muted/60 p-8 text-center space-y-4 mt-2">
            <p className="text-[15px] font-semibold text-foreground">거래 기록이 없어요</p>
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              우측 하단 버튼을 눌러<br />첫 거래를 기록해보세요
            </p>
          </div>
        ) : filteredTrades.length === 0 ? (
          <div className="rounded-2xl bg-muted/60 p-8 text-center space-y-4 mt-2">
            <p className="text-[15px] font-semibold text-foreground">해당 계좌의 기록이 없어요</p>
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              다른 계좌를 선택하거나<br />새 거래를 기록해보세요
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
                      onPress={() => openTrade({ trade, accounts, allTrades: trades })}
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
      <TradeFormPanel
        open={formOpen}
        onOpenChange={setFormOpen}
        accounts={accounts}
      />
    </>
  );
}
