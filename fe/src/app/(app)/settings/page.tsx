"use client";

import { useQuery } from "@tanstack/react-query";
import { accountsApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useAuth } from "@/components/providers/AuthProvider";
import { AccountList } from "@/components/settings/AccountList";
import { UserInfoSection } from "@/components/settings/UserInfoSection";
import { DeleteAccountSection } from "@/components/settings/DeleteAccountSection";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";

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
        <ErrorState onRetry={refetch} />
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

        <section className="space-y-3">
          <h2 className="text-[13px] font-semibold text-muted-foreground px-1">계정</h2>
          <DeleteAccountSection />
        </section>

        <p className="text-xs text-center text-muted-foreground">
          투자노트 v{process.env.NEXT_PUBLIC_APP_VERSION}
        </p>
      </div>
    </>
  );
}
