"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { TradeCard } from "./TradeCard";
import { TradeFormPanel } from "./TradeFormPanel";
import { useDetailPanel } from "@/components/panels/DetailPanelProvider";
import { CsvUploadButton } from "./CsvUploadButton";
import { ImportTradesPanel } from "./ImportTradesPanel";
import { Button } from "@/components/base/Button";
import { AccountFilter } from "@/components/shared/AccountFilter";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";
import { Checkbox } from "@/components/base/Checkbox";
import { useAccountFilter, useEffectiveAccountId } from "@/components/providers/AccountFilterProvider";
import { useHideBottomNav } from "@/components/providers/BottomNavProvider";
import { useTradeSelection } from "@/hooks/useTradeSelection";
import { useDialogState } from "@/hooks/useDialogState";
import { tradesApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
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
  const queryClient = useQueryClient();

  const selection = useTradeSelection();
  const { isSelectMode, selectedIds, enter, exit, toggle, selectAll, clearAll } = selection;
  const bulkDeleteDialog = useDialogState();
  const singleDeleteDialog = useDialogState();
  // 단건 삭제 다이얼로그가 띄워진 대상 trade. 다이얼로그 표시 도중 trade 가
  // 사라지는 좁은 race 에 대비해 따로 보관한다.
  const [pendingDelete, setPendingDelete] = useState<TradeWithAccount | null>(null);
  // 스와이프가 열린 카드 ID. 한 번에 하나만 열린다.
  const [openSwipeId, setOpenSwipeId] = useState<string | null>(null);
  useHideBottomNav(isSelectMode);

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
      effectiveAccountId === null
        ? trades
        : trades.filter((t) => t.account_id === effectiveAccountId),
    [trades, effectiveAccountId],
  );

  const grouped = useMemo(() => groupByDate(filteredTrades), [filteredTrades]);

  // AccountFilter 변경 시 선택/열린 스와이프 모두 초기화 (모드는 유지).
  // effectiveAccountId 는 사용자 필터 변경 외에 accounts refetch 결과로도 바뀔 수 있어
  // 단일 이벤트 핸들러로 옮길 수 없음.
  useEffect(() => {
    clearAll();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOpenSwipeId(null);
  }, [effectiveAccountId, clearAll]);

  // 선택 모드에 진입하면 열린 스와이프 카드가 시각적으로 어색하므로 닫는다.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (isSelectMode) setOpenSwipeId(null);
  }, [isSelectMode]);

  // 페이지 스크롤 시 열린 카드를 닫는다.
  useEffect(() => {
    if (openSwipeId === null) return;
    const onScroll = () => setOpenSwipeId(null);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [openSwipeId]);

  const handleTradePress = useCallback(
    (trade: TradeWithAccount) => openTrade({ trade, accounts, allTrades: trades }),
    [openTrade, accounts, trades],
  );

  const handleSwipeOpenChange = useCallback((id: string, open: boolean) => {
    setOpenSwipeId((current) => {
      if (open) return id;
      return current === id ? null : current;
    });
  }, []);

  const handleRequestDelete = useCallback(
    (trade: TradeWithAccount) => {
      setPendingDelete(trade);
      singleDeleteDialog.setOpen(true);
    },
    [singleDeleteDialog],
  );

  const allSelected =
    filteredTrades.length > 0 && selectedIds.size === filteredTrades.length;
  const selectedCount = selectedIds.size;

  const onToggleSelectAll = useCallback(() => {
    if (allSelected) clearAll();
    else selectAll(filteredTrades.map((t) => t.id));
  }, [allSelected, clearAll, selectAll, filteredTrades]);

  const onConfirmBulkDelete = useCallback(
    () =>
      bulkDeleteDialog.run(async () => {
        const ids = [...selectedIds];
        // 다이얼로그 표시 도중 accounts refetch → useEffect clearAll 로 selection 이 비워진
        // 좁은 race 에 대비. 빈 배열로 호출하면 BE 가 422 로 응답해 사용자에게 무의미한
        // 에러를 노출하므로 여기서 조용히 다이얼로그만 닫는다.
        if (ids.length === 0) {
          bulkDeleteDialog.setOpen(false);
          return;
        }
        await tradesApi.bulkDelete(ids);
        // BUY meta cascade → trades + portfolio + analysis 모두 무효화.
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
          queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
          queryClient.invalidateQueries({ queryKey: ["analysis"] }),
        ]);
        toast.success(`${ids.length}건의 거래를 삭제했어요`);
        exit();
      }, "삭제할 수 없습니다."),
    [bulkDeleteDialog, selectedIds, queryClient, exit],
  );

  const onConfirmSingleDelete = useCallback(
    () =>
      singleDeleteDialog.run(async () => {
        // 다이얼로그 표시 도중 race 로 pendingDelete 가 사라진 경우 조용히 닫는다.
        const target = pendingDelete;
        if (!target) {
          singleDeleteDialog.setOpen(false);
          return;
        }
        await tradesApi.delete(target.id);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
          queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
          queryClient.invalidateQueries({ queryKey: ["analysis"] }),
        ]);
        toast.success("거래를 삭제했어요");
        setOpenSwipeId(null);
        setPendingDelete(null);
      }, "삭제할 수 없습니다."),
    [singleDeleteDialog, pendingDelete, queryClient],
  );

  return (
    <>
      <div className="sticky top-0 z-10 bg-background">
        {isSelectMode ? (
          <PageHeader sticky={false}>
            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={exit}
                className="text-[14px] font-medium text-foreground px-2 py-1 -mx-2"
              >
                취소
              </button>
              <span className="text-[15px] font-bold text-foreground tabular-nums">
                {selectedCount}개 선택됨
              </span>
              <button
                type="button"
                onClick={() => bulkDeleteDialog.setOpen(true)}
                disabled={selectedCount === 0}
                className="text-[14px] font-semibold text-destructive disabled:text-muted-foreground px-2 py-1 -mx-2"
              >
                삭제
              </button>
            </div>
          </PageHeader>
        ) : (
          <PageHeader
            title="기록"
            actions={
              <div className="flex items-center gap-1.5">
                <CsvUploadButton onClick={openImport} />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => enter()}
                  disabled={filteredTrades.length === 0}
                >
                  선택
                </Button>
              </div>
            }
            sticky={false}
          />
        )}

        {isSelectMode && filteredTrades.length > 0 && (
          <div className="flex items-center gap-2 px-5 pb-2">
            <label className="inline-flex items-center gap-2 text-[13px] text-muted-foreground cursor-pointer select-none">
              <Checkbox checked={allSelected} onCheckedChange={onToggleSelectAll} />
              {allSelected ? "전체 해제" : "전체 선택"}
            </label>
          </div>
        )}

        {accounts.length >= 2 && (
          <AccountFilter
            accounts={accounts}
            value={effectiveAccountId}
            onChange={setSelectedAccountId}
          />
        )}
      </div>

      <div
        className="px-5 pb-6"
        onClick={() => setOpenSwipeId(null)}
      >
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
                      onPress={handleTradePress}
                      selectionMode={isSelectMode}
                      selected={selectedIds.has(trade.id)}
                      onSelectToggle={toggle}
                      swipeOpen={openSwipeId === trade.id}
                      onSwipeOpenChange={handleSwipeOpenChange}
                      onRequestDelete={handleRequestDelete}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* FAB — 선택 모드에서는 숨김 */}
      {!isSelectMode && (
        <button
          type="button"
          onClick={openForm}
          className="fixed bottom-28 right-5 z-20 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg active:scale-95 transition-transform"
          aria-label="거래 등록"
        >
          <PlusIcon className="h-6 w-6" strokeWidth={2.5} />
        </button>
      )}

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

      <ConfirmDeleteDialog
        open={bulkDeleteDialog.open}
        onOpenChange={bulkDeleteDialog.setOpen}
        title="거래 일괄 삭제"
        description={
          <>
            선택한 <strong>{selectedCount}건</strong>의 거래를 삭제하시겠습니까?
            <br />
            이 작업은 되돌릴 수 없습니다.
          </>
        }
        pending={bulkDeleteDialog.pending}
        error={bulkDeleteDialog.error}
        onConfirm={onConfirmBulkDelete}
      />

      <ConfirmDeleteDialog
        open={singleDeleteDialog.open}
        onOpenChange={(open) => {
          singleDeleteDialog.setOpen(open);
          if (!open) setPendingDelete(null);
        }}
        title="거래 삭제"
        description={
          <>
            <strong>{pendingDelete?.asset_name ?? ""}</strong> 거래를 삭제하시겠습니까?
            <br />
            이 작업은 되돌릴 수 없습니다.
          </>
        }
        pending={singleDeleteDialog.pending}
        error={singleDeleteDialog.error}
        onConfirm={onConfirmSingleDelete}
      />
    </>
  );
}
