import { notFound, redirect } from "next/navigation";
import { serverFetch } from "@/lib/api-server/server-fetch";
import { StockDetail } from "@/components/stocks/StockDetail";
import type { Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";
import { createClient } from "@/lib/supabase/server";

interface StockDetailPageProps {
  params: Promise<{ country: string; ticker: string }>;
}

export default async function StockDetailPage({ params }: StockDetailPageProps) {
  const { country, ticker } = await params;

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const res = await serverFetch(
    `/api/trades?ticker=${encodeURIComponent(ticker.toUpperCase())}&country=${encodeURIComponent(country.toUpperCase())}`
  );
  if (!res.ok) notFound();

  const { trades }: { trades: TradeWithAccount[]; accounts: Account[] } = await res.json();

  if (!trades || trades.length === 0) notFound();

  const assetName = trades[0].asset_name;
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
