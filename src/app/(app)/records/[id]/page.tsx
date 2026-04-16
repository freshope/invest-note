import { notFound, redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { TradeDetail } from "@/components/records/TradeDetail";
import type { Trade, Account } from "@/types/database";

interface TradeDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function TradeDetailPage({ params }: TradeDetailPageProps) {
  const { id } = await params;

  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  const { data: tradeRaw } = await supabase
    .from("trades")
    .select("*, accounts(name, broker)")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  if (!tradeRaw) {
    notFound();
  }

  const { accounts: acc, ...trade } = tradeRaw as Trade & { accounts: { name: string; broker: string | null } | null };
  const tradeWithAccount = { ...trade, account: acc ?? undefined };

  const { data: accounts } = await supabase
    .from("accounts")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: true });

  return (
    <TradeDetail
      trade={tradeWithAccount}
      accounts={(accounts ?? []) as Account[]}
    />
  );
}
