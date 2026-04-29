"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Account } from "@/types/database";

export const ACCOUNT_FILTER_ALL = "all" as const;

interface AccountFilterContextValue {
  selectedAccountId: string;
  setSelectedAccountId: (id: string) => void;
}

const AccountFilterContext = createContext<AccountFilterContextValue | null>(null);

export function AccountFilterProvider({ children }: { children: React.ReactNode }) {
  const [selectedAccountId, setSelectedAccountId] = useState<string>(ACCOUNT_FILTER_ALL);

  const value = useMemo(
    () => ({ selectedAccountId, setSelectedAccountId }),
    [selectedAccountId],
  );

  return (
    <AccountFilterContext.Provider value={value}>
      {children}
    </AccountFilterContext.Provider>
  );
}

export function useAccountFilter() {
  const ctx = useContext(AccountFilterContext);
  if (!ctx) throw new Error("useAccountFilter must be used within AccountFilterProvider");
  return ctx;
}

export function useEnsureValidAccount(accounts: Account[]) {
  const { selectedAccountId, setSelectedAccountId } = useAccountFilter();
  useEffect(() => {
    if (selectedAccountId === ACCOUNT_FILTER_ALL) return;
    if (!accounts.some((a) => a.id === selectedAccountId)) {
      setSelectedAccountId(ACCOUNT_FILTER_ALL);
    }
  }, [accounts, selectedAccountId, setSelectedAccountId]);
}
