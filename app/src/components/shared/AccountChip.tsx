"use client";

import { cn } from "@/lib/utils";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import type { Account } from "@/types/database";

type AccountChipSize = "sm" | "md" | "lg";

const SIZE_PX: Record<AccountChipSize, number> = {
  sm: 14,
  md: 16,
  lg: 20,
};

const GAP: Record<AccountChipSize, string> = {
  sm: "gap-1",
  md: "gap-1.5",
  lg: "gap-1.5",
};

interface AccountChipProps {
  account: Pick<Account, "broker" | "name">;
  size?: AccountChipSize;
  className?: string;
}

export function AccountChip({ account, size = "md", className }: AccountChipProps) {
  return (
    <span className={cn("inline-flex max-w-full min-w-0 items-center", GAP[size], className)}>
      {account.broker && <BrokerLogo broker={account.broker} size={SIZE_PX[size]} />}
      <span className="min-w-0 truncate">{account.name}</span>
    </span>
  );
}
