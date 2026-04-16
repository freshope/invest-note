import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { AccountList } from "@/components/settings/AccountList";
import { UserInfoSection } from "@/components/settings/UserInfoSection";

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: accounts } = await supabase
    .from("accounts")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: true });

  // 계좌별 거래 수 조회 (삭제 가능 여부 판단)
  const tradeCounts: Record<string, number> = {};
  if (accounts && accounts.length > 0) {
    const { data: counts } = await supabase
      .from("trades")
      .select("account_id")
      .eq("user_id", user.id)
      .in("account_id", accounts.map((a) => a.id));

    if (counts) {
      for (const trade of counts) {
        tradeCounts[trade.account_id] = (tradeCounts[trade.account_id] ?? 0) + 1;
      }
    }
  }

  // cash_balance: Supabase numeric → number 변환
  const normalizedAccounts = (accounts ?? []).map((a) => ({
    ...a,
    cash_balance: Number(a.cash_balance),
  }));

  return (
    <div className="px-5 py-8 space-y-10">
      <h1 className="text-2xl font-bold text-foreground">설정</h1>

      <section className="space-y-3">
        <h2 className="text-[13px] font-semibold text-muted-foreground px-1">계좌 관리</h2>
        <AccountList accounts={normalizedAccounts} tradeCounts={tradeCounts} />
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
