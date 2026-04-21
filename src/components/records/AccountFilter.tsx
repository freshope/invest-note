"use client";

import { cn } from "@/lib/utils";
import type { Account } from "@/types/database";

interface AccountFilterProps {
  accounts: Account[];
  value: string;
  onChange: (value: string) => void;
}

export function AccountFilter({ accounts, value, onChange }: AccountFilterProps) {
  const chips = [{ id: "all", name: "전체" }, ...accounts.map((a) => ({ id: a.id, name: a.name }))];

  return (
    <div className="flex gap-2 overflow-x-auto scrollbar-hide px-5 pb-3">
      {chips.map((chip) => (
        <button
          key={chip.id}
          type="button"
          onClick={() => onChange(chip.id)}
          className={cn(
            "shrink-0 rounded-full px-3.5 py-1 text-[13px] font-medium transition-colors",
            value === chip.id
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          )}
        >
          {chip.name}
        </button>
      ))}
    </div>
  );
}
