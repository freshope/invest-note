"use client";

import { useQuery } from "@tanstack/react-query";
import { accountsApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useAuth } from "@/components/providers/AuthProvider";
import { AccountList } from "@/components/settings/AccountList";
import { UserInfoSection } from "@/components/settings/UserInfoSection";
import { PageHeader } from "@/components/layout/PageHeader";

export default function SettingsPage() {
  const { user } = useAuth();

  const { data: accounts, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: accountsApi.list,
  });

  if (isLoading) {
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

  if (isError) {
    return (
      <>
        <PageHeader title="설정" />
        <div className="px-5 pt-6 text-center space-y-3">
          <p className="text-[13px] text-muted-foreground">데이터를 불러오지 못했어요.</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="text-primary text-[13px] font-medium"
          >
            다시 시도
          </button>
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
          <AccountList accounts={accounts ?? []} />
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
