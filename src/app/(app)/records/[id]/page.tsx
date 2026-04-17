import { notFound, redirect } from "next/navigation";
import { serverFetch } from "@/lib/api-server/server-fetch";
import { TradeDetail } from "@/components/records/TradeDetail";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";
import { createClient } from "@/lib/supabase/server";

interface TradeDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function TradeDetailPage({ params }: TradeDetailPageProps) {
  const { id } = await params;

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [tradeRes, accountsRes] = await Promise.all([
    serverFetch(`/api/trades/${id}`),
    serverFetch("/api/accounts"),
  ]);

  if (!tradeRes.ok) notFound();

  const trade: TradeWithAccount = await tradeRes.json();
  const accounts: Account[] = accountsRes.ok ? await accountsRes.json() : [];

  return <TradeDetail trade={trade} accounts={accounts} />;
}
