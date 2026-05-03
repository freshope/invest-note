"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { AccountFormPanel } from "./AccountFormPanel";
import { AccountChip } from "@/components/shared/AccountChip";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";
import { accountsApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { fmt } from "@/lib/format";
import type { Account } from "@/types/database";

interface AccountCardProps {
  account: Account;
  tradeCount: number;
}

export function AccountCard({ account, tradeCount }: AccountCardProps) {
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const cashBalance = Number(account.cash_balance);

  async function handleDeleteConfirm() {
    setDeleteError(null);
    setDeletePending(true);
    try {
      await accountsApi.delete(account.id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts }),
        queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
      ]);
      setDeleteOpen(false);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "삭제할 수 없습니다.");
    } finally {
      setDeletePending(false);
    }
  }

  return (
    <>
      <div className="rounded-2xl bg-muted/60 p-5 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <AccountChip
              account={account}
              size="lg"
              className="text-[17px] font-bold text-foreground leading-tight"
            />
          </div>
          <div className="flex gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setEditOpen(true)}
              className="text-[13px] h-8 px-3 text-muted-foreground hover:text-foreground"
            >
              수정
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeleteOpen(true)}
              disabled={tradeCount > 0}
              title={tradeCount > 0 ? "거래 기록이 있는 계좌는 삭제할 수 없습니다" : undefined}
              className={
                tradeCount > 0
                  ? "text-[13px] h-8 px-3 opacity-30 cursor-not-allowed"
                  : "text-[13px] h-8 px-3 text-destructive hover:text-destructive hover:bg-destructive/10"
              }
            >
              삭제
            </Button>
          </div>
        </div>

        <div className="pt-1 border-t border-border/60">
          <p className="text-[13px] text-muted-foreground">예수금</p>
          <p className="text-[18px] font-bold text-foreground tabular-nums mt-0.5">
            {fmt(cashBalance)}원
          </p>
        </div>

        {tradeCount > 0 && (
          <p className="text-[12px] text-muted-foreground">거래 {tradeCount}건</p>
        )}
      </div>

      <AccountFormPanel
        open={editOpen}
        onOpenChange={setEditOpen}
        account={account}
      />

      {deleteOpen && (
        <ConfirmDeleteDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          title="계좌 삭제"
          description={
            <>
              <strong>{account.name}</strong>을(를) 삭제하시겠습니까?
              <br />
              이 작업은 되돌릴 수 없습니다.
            </>
          }
          pending={deletePending}
          error={deleteError}
          onConfirm={handleDeleteConfirm}
        />
      )}
    </>
  );
}
