"use client";

import { useQuery } from "@tanstack/react-query";
import { accountsApi, tradesApi } from "@/lib/api-client";
import { useAuth } from "@/components/providers/AuthProvider";
import { AccountList } from "@/components/settings/AccountList";
import { UserInfoSection } from "@/components/settings/UserInfoSection";
import { PageHeader } from "@/components/layout/PageHeader";

export default function SettingsPage() {
  const { user } = useAuth();

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountsApi.list,
  });

  const { data: tradesData, isLoading: tradesLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: () => tradesApi.list(),
  });

  const loading = accountsLoading || tradesLoading;

  const countMap: Record<string, number> = {};
  if (tradesData) {
    for (const t of tradesData.trades) {
      countMap[t.account_id] = (countMap[t.account_id] ?? 0) + 1;
    }
  }

  if (loading) {
    return (
      <>
        <PageHeader title="설정" />
        <div className="px-5 pt-2 pb-6 space-y-4 animate-pulse">
          {[0, 1].map((i) => (
            <div key={i} className="rounded-2xl bg-muted/60 h-24" />
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="설정" />
      <div className="px-5 pt-2 pb-8 space-y-10">
        <section className="space-y-3">
          <h2 className="text-[13px] font-semibold text-muted-foreground px-1">계좌 관리</h2>
          <AccountList accounts={accounts ?? []} tradeCounts={countMap} />
        </section>

        <section className="space-y-3">
          <h2 className="text-[13px] font-semibold text-muted-foreground px-1">내 정보</h2>
          <UserInfoSection email={user?.email ?? ""} />
        </section>

        <p className="text-xs text-center text-muted-foreground">
          투자노트 v0.1.0
        </p>
      </div>
    </>
  );
}
