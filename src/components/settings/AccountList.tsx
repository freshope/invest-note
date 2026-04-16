"use client";

import { useState } from "react";
import { Button } from "@/components/base/Button";
import { AccountCard } from "./AccountCard";
import { AccountFormPanel } from "./AccountFormPanel";
import type { Account } from "@/types/database";

interface AccountListProps {
  accounts: Account[];
  tradeCounts: Record<string, number>;
}

export function AccountList({ accounts, tradeCounts }: AccountListProps) {
  const [addOpen, setAddOpen] = useState(false);

  return (
    <>
      <div className="space-y-3">
        {accounts.length === 0 ? (
          <div className="rounded-2xl bg-muted/60 p-8 text-center space-y-4">
            <p className="text-[15px] font-semibold text-foreground">등록된 계좌가 없어요</p>
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              계좌를 추가하면 거래 기록을<br />계좌별로 관리할 수 있어요
            </p>
            <Button
              variant="default"
              onClick={() => setAddOpen(true)}
              className="mt-2 px-5"
            >
              첫 계좌 추가하기
            </Button>
          </div>
        ) : (
          <>
            {accounts.map((account) => (
              <AccountCard
                key={account.id}
                account={account}
                tradeCount={tradeCounts[account.id] ?? 0}
              />
            ))}
            <button
              type="button"
              onClick={() => setAddOpen(true)}
              className="w-full rounded-2xl border-2 border-dashed border-border py-4 text-[14px] font-semibold text-muted-foreground hover:border-primary/50 hover:text-primary transition-colors"
            >
              + 계좌 추가
            </button>
          </>
        )}
      </div>

      {addOpen && (
        <AccountFormPanel open={addOpen} onOpenChange={setAddOpen} />
      )}
    </>
  );
}
