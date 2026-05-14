"use client";

import { cn } from "@/lib/utils";
import { AccountChip } from "@/components/shared/AccountChip";
import type { Account } from "@/types/database";

interface AccountFilterProps {
  accounts: Account[];
  value: string | null;
  onChange: (value: string | null) => void;
}

function chipClass(active: boolean, extra?: string) {
  return cn(
    "shrink-0 rounded-full text-[13px] font-medium transition-colors",
    active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80",
    extra
  );
}

export function AccountFilter({ accounts, value, onChange }: AccountFilterProps) {
  return (
    <div className="flex gap-2 overflow-x-auto scrollbar-hide px-5 pb-3">
      <button
        type="button"
        onClick={() => onChange(null)}
        className={chipClass(value === null, "px-3.5 py-1")}
      >
        전체
      </button>
      {accounts.map((acc) => (
        <button
          key={acc.id}
          type="button"
          onClick={() => onChange(acc.id)}
          className={chipClass(value === acc.id, "pl-1.5 pr-3.5 py-1")}
        >
          <AccountChip account={acc} size="md" />
        </button>
      ))}
    </div>
  );
}
