import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { TradeList } from "@/components/records/TradeList";
import type { Account, Trade } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

export default async function RecordsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [{ data: tradesRaw, error: tradesError }, { data: accountsRaw, error: accountsError }] = await Promise.all([
    supabase
      .from("trades")
      .select("*, accounts(name, broker)")
      .eq("user_id", user.id)
      .order("traded_at", { ascending: false }),
    supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: true }),
  ]);

  if (tradesError || accountsError) throw new Error("데이터를 불러오는 중 오류가 발생했어요");

  const trades: TradeWithAccount[] = (tradesRaw ?? []).map((t) => {
    const { accounts: acc, ...trade } = t as Trade & {
      accounts: { name: string; broker: string | null } | null;
    };
    return { ...trade, account: acc ?? undefined };
  });

  const accounts: Account[] = (accountsRaw ?? []).map((a) => ({
    ...a,
    cash_balance: Number(a.cash_balance),
  }));

  return <TradeList trades={trades} accounts={accounts} />;
}
