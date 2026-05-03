"use client";

import { createContext, useContext, useMemo, useState } from "react";
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

// 컨슈머가 항상 정상화된 값(=현재 accounts 에 존재하는 id 또는 ALL)만 사용하도록
// derive 헬퍼를 제공한다. 기존 useEnsureValidAccount 의 setState-in-effect 와 달리,
// 글로벌 raw selectedAccountId 가 stale 인 채로 남아도 어떤 컨슈머도 stale 을 보지 않는다.
//
// 컨벤션: filter 비교/표시는 항상 useEffectiveAccountId 를 사용한다.
// raw selectedAccountId 를 직접 read 하면 stale 을 볼 수 있다.
export function useEffectiveAccountId(accounts: Account[]): string {
  const { selectedAccountId } = useAccountFilter();
  if (selectedAccountId === ACCOUNT_FILTER_ALL) return ACCOUNT_FILTER_ALL;
  return accounts.some((a) => a.id === selectedAccountId)
    ? selectedAccountId
    : ACCOUNT_FILTER_ALL;
}
