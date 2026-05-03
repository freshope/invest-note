"use client";

import { useCallback, useMemo, useState } from "react";
import { TradeCard } from "./TradeCard";
import { TradeFormPanel } from "./TradeFormPanel";
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import { CsvUploadButton } from "./CsvUploadButton";
import { ImportTradesPanel } from "./ImportTradesPanel";
import { AccountFilter } from "@/components/shared/AccountFilter";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { ACCOUNT_FILTER_ALL, useAccountFilter, useEffectiveAccountId } from "@/components/providers/AccountFilterProvider";
import { groupByDate, formatDateLabel, type TradeWithAccount } from "@/lib/trade-utils";
import type { Account } from "@/types/database";
import { PlusIcon } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";

interface TradeListProps {
  trades: TradeWithAccount[];
  accounts: Account[];
}

export function TradeList({ trades, accounts }: TradeListProps) {
  // 패널을 닫을 때 같은 인스턴스가 슬라이드 아웃 애니메이션을 끝까지 유지하도록
  // open 자체로 unmount 하지 않고, 다시 열 때만 key 를 ++ 해 새 인스턴스를 마운트한다.
  const [formOpen, setFormOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [importOpen, setImportOpen] = useState(false);
  const [importKey, setImportKey] = useState(0);
  const { setSelectedAccountId } = useAccountFilter();
  const effectiveAccountId = useEffectiveAccountId(accounts);
  const { openTrade } = useDetailPanel();

  const openForm = useCallback(() => {
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const openImport = useCallback(() => {
    setImportKey((k) => k + 1);
    setImportOpen(true);
  }, []);

  const filteredTrades = useMemo(
    () =>
      effectiveAccountId === ACCOUNT_FILTER_ALL
        ? trades
        : trades.filter((t) => t.account_id === effectiveAccountId),
    [trades, effectiveAccountId],
  );

  const grouped = useMemo(() => groupByDate(filteredTrades), [filteredTrades]);

  return (
    <>
      <div className="sticky top-0 z-10 bg-background">
        <PageHeader title="기록" actions={<CsvUploadButton onClick={openImport} />} sticky={false} />
        {accounts.length >= 2 && (
          <AccountFilter
            accounts={accounts}
            value={effectiveAccountId}
            onChange={setSelectedAccountId}
          />
        )}
      </div>

      <div className="px-5 pb-6">
        {trades.length === 0 ? (
          <EmptyCard
            className="mt-2"
            title="거래 기록이 없어요"
            description={
              <>
                우측 하단 버튼을 눌러<br />첫 거래를 기록해보세요
              </>
            }
          />
        ) : filteredTrades.length === 0 ? (
          <EmptyCard
            className="mt-2"
            title="해당 계좌의 기록이 없어요"
            description={
              <>
                다른 계좌를 선택하거나<br />새 거래를 기록해보세요
              </>
            }
          />
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
        onClick={openForm}
        className="fixed bottom-28 right-5 z-20 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg active:scale-95 transition-transform"
        aria-label="거래 등록"
      >
        <PlusIcon className="h-6 w-6" strokeWidth={2.5} />
      </button>

      {/* 거래 등록 패널 */}
      <TradeFormPanel
        key={`form-${formKey}`}
        open={formOpen}
        onOpenChange={setFormOpen}
        accounts={accounts}
      />

      {/* 거래내역서 일괄 import 패널 */}
      <ImportTradesPanel
        key={`import-${importKey}`}
        open={importOpen}
        onOpenChange={setImportOpen}
        accounts={accounts}
      />
    </>
  );
}
