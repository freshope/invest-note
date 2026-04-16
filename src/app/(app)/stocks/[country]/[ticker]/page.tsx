import { notFound, redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { StockDetail } from "@/components/stocks/StockDetail";
import type { Trade, Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

interface StockDetailPageProps {
  params: Promise<{ country: string; ticker: string }>;
}

export default async function StockDetailPage({ params }: StockDetailPageProps) {
  const { country, ticker } = await params;

  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  const { data: tradesRaw } = await supabase
    .from("trades")
    .select("*, accounts(name, broker)")
    .eq("user_id", user.id)
    .eq("country_code", country.toUpperCase())
    .eq("ticker_symbol", ticker.toUpperCase())
    .order("traded_at", { ascending: false });

  if (!tradesRaw || tradesRaw.length === 0) {
    notFound();
  }

  const trades: TradeWithAccount[] = tradesRaw.map((t) => {
    const { accounts: acc, ...trade } = t as Trade & { accounts: { name: string; broker: string | null } | null };
    return { ...trade, account: acc ?? undefined };
  });

  const assetName = trades[0].asset_name;

  // 성과 계산
  const sellTrades = trades.filter((t) => t.trade_type === "SELL");
  const winCount = sellTrades.filter((t) => t.result === "SUCCESS").length;
  const totalProfitLoss = sellTrades.reduce((sum, t) => sum + (t.profit_loss ? Number(t.profit_loss) : 0), 0);

  const stats = {
    totalTrades: trades.length,
    sellCount: sellTrades.length,
    winCount,
    totalProfitLoss,
  };

  return (
    <StockDetail
      assetName={assetName}
      ticker={ticker.toUpperCase()}
      country={country.toUpperCase()}
      trades={trades}
      stats={stats}
    />
  );
}
