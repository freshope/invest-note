import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { TradeList } from "@/components/records/TradeList";
import type { Trade, Account } from "@/types/database";

type TradeWithAccount = Trade & { account?: Pick<Account, "name" | "broker"> };

export default async function RecordsPage() {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  // 거래 목록 조회 (계좌 정보 join)
  const { data: tradesRaw } = await supabase
    .from("trades")
    .select("*, accounts(name, broker)")
    .eq("user_id", user.id)
    .order("traded_at", { ascending: false });

  // 계좌 목록 조회 (폼 드롭다운용)
  const { data: accounts } = await supabase
    .from("accounts")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: true });

  // account join 데이터 정규화
  const trades: TradeWithAccount[] = (tradesRaw ?? []).map((t) => {
    const { accounts: acc, ...trade } = t as Trade & { accounts: { name: string; broker: string | null } | null };
    return {
      ...trade,
      account: acc ?? undefined,
    };
  });

  return (
    <TradeList
      trades={trades}
      accounts={(accounts ?? []) as Account[]}
    />
  );
}
