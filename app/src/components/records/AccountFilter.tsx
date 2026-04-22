"use client";

import { cn } from "@/lib/utils";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import type { Account } from "@/types/database";

interface AccountFilterProps {
  accounts: Account[];
  value: string;
  onChange: (value: string) => void;
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
        onClick={() => onChange("all")}
        className={chipClass(value === "all", "px-3.5 py-1")}
      >
        전체
      </button>
      {accounts.map((acc) => (
        <button
          key={acc.id}
          type="button"
          onClick={() => onChange(acc.id)}
          className={chipClass(value === acc.id, "inline-flex items-center gap-1.5 pl-1.5 pr-3.5 py-1")}
        >
          {acc.broker && <BrokerLogo broker={acc.broker} size={18} />}
          {acc.name}
        </button>
      ))}
    </div>
  );
}
