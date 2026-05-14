"use client";

import { useState } from "react";
import { Button } from "@/components/base/Button";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { AccountCard } from "./AccountCard";
import { AccountFormPanel } from "./AccountFormPanel";
import type { Account } from "@/types/database";

interface AccountListProps {
  accounts: Account[];
}

export function AccountList({ accounts }: AccountListProps) {
  const [addOpen, setAddOpen] = useState(false);

  return (
    <>
      <div className="space-y-3">
        {accounts.length === 0 ? (
          <EmptyCard
            title="등록된 계좌가 없어요"
            description={
              <>
                계좌를 추가하면 거래 기록을<br />계좌별로 관리할 수 있어요
              </>
            }
            action={
              <Button
                variant="default"
                onClick={() => setAddOpen(true)}
                className="mt-2 px-5"
              >
                첫 계좌 추가하기
              </Button>
            }
          />
        ) : (
          <>
            {accounts.map((account) => (
              <AccountCard
                key={account.id}
                account={account}
                tradeCount={account.trade_count ?? 0}
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

      <AccountFormPanel open={addOpen} onOpenChange={setAddOpen} />
    </>
  );
}
