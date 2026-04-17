import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/api-server/server-fetch";
import { TradeList } from "@/components/records/TradeList";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";
import { createClient } from "@/lib/supabase/server";

export default async function RecordsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const res = await serverFetch("/api/trades");
  const { trades, accounts }: { trades: TradeWithAccount[]; accounts: Account[] } =
    res.ok ? await res.json() : { trades: [], accounts: [] };

  return <TradeList trades={trades} accounts={accounts} />;
}
