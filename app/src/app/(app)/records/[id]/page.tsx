import { notFound, redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { TradeDetail } from "@/components/records/TradeDetail";
import type { Account, Trade } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

interface TradeDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function TradeDetailPage({ params }: TradeDetailPageProps) {
  const { id } = await params;

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [{ data: tradeRaw, error }, { data: accountsRaw }] = await Promise.all([
    supabase
      .from("trades")
      .select("*, accounts(name, broker)")
      .eq("id", id)
      .eq("user_id", user.id)
      .single(),
    supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: true }),
  ]);

  if (error || !tradeRaw) notFound();

  const { accounts: acc, ...rest } = tradeRaw as Trade & {
    accounts: { name: string; broker: string | null } | null;
  };
  const trade: TradeWithAccount = { ...rest, account: acc ?? undefined };
  const accounts: Account[] = (accountsRaw ?? []).map((a) => ({
    ...a,
    cash_balance: Number(a.cash_balance),
  }));

  return <TradeDetail trade={trade} accounts={accounts} />;
}
