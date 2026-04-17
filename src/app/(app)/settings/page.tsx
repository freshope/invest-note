import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/api-server/server-fetch";
import { AccountList } from "@/components/settings/AccountList";
import { UserInfoSection } from "@/components/settings/UserInfoSection";
import type { Account } from "@/types/database";
import { createClient } from "@/lib/supabase/server";

type AccountWithCount = Account & { trade_count: number };

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const res = await serverFetch("/api/accounts");
  const accounts: AccountWithCount[] = res.ok ? await res.json() : [];

  const tradeCounts: Record<string, number> = {};
  for (const a of accounts) {
    tradeCounts[a.id] = a.trade_count;
  }

  return (
    <div className="px-5 py-8 space-y-10">
      <h1 className="text-2xl font-bold text-foreground">설정</h1>

      <section className="space-y-3">
        <h2 className="text-[13px] font-semibold text-muted-foreground px-1">계좌 관리</h2>
        <AccountList accounts={accounts} tradeCounts={tradeCounts} />
      </section>

      <section className="space-y-3">
        <h2 className="text-[13px] font-semibold text-muted-foreground px-1">내 정보</h2>
        <UserInfoSection email={user.email ?? ""} />
      </section>

      <p className="text-xs text-center text-muted-foreground">
        투자노트 v0.1.0
      </p>
    </div>
  );
}
