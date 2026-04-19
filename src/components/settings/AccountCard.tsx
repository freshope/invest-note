"use client";

import { useState } from "react";
import { Button } from "@/components/base/Button";
import { AccountFormPanel } from "./AccountFormPanel";
import { DeleteAccountDialog } from "./DeleteAccountDialog";
import type { Account } from "@/types/database";

function formatKRW(amount: number): string {
  return new Intl.NumberFormat("ko-KR").format(amount) + "원";
}

interface AccountCardProps {
  account: Account;
  tradeCount: number;
}

export function AccountCard({ account, tradeCount }: AccountCardProps) {
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const cashBalance = Number(account.cash_balance);

  return (
    <>
      <div className="rounded-2xl bg-muted/60 p-5 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[17px] font-bold text-foreground truncate leading-tight">
              {account.name}
            </p>
            {account.broker && (
              <p className="text-[13px] text-muted-foreground mt-0.5">{account.broker}</p>
            )}
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
            {formatKRW(cashBalance)}
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
        <DeleteAccountDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          accountId={account.id}
          accountName={account.name}
        />
      )}
    </>
  );
}
