import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AccountList } from "@/components/settings/AccountList";
import { UserInfoSection } from "@/components/settings/UserInfoSection";
import type { Account } from "@/types/database";

type AccountWithCount = Account & { trade_count: number };

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [{ data: accountsRaw }, { data: tradeCounts }] = await Promise.all([
    supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: true }),
    supabase
      .from("trades")
      .select("account_id")
      .eq("user_id", user.id),
  ]);

  const countMap: Record<string, number> = {};
  for (const t of tradeCounts ?? []) {
    countMap[t.account_id] = (countMap[t.account_id] ?? 0) + 1;
  }

  const accounts: AccountWithCount[] = (accountsRaw ?? []).map((a) => ({
    ...a,
    cash_balance: Number(a.cash_balance),
    trade_count: countMap[a.id] ?? 0,
  }));

  return (
    <div className="px-5 py-8 space-y-10">
      <h1 className="text-2xl font-bold text-foreground">설정</h1>

      <section className="space-y-3">
        <h2 className="text-[13px] font-semibold text-muted-foreground px-1">계좌 관리</h2>
        <AccountList accounts={accounts} tradeCounts={countMap} />
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
