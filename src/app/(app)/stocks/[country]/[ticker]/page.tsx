import { notFound, redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { StockDetail } from "@/components/stocks/StockDetail";
import type { Trade } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

interface StockDetailPageProps {
  params: Promise<{ country: string; ticker: string }>;
}

export default async function StockDetailPage({ params }: StockDetailPageProps) {
  const { country, ticker } = await params;
  const tickerUpper = ticker.toUpperCase();
  const countryUpper = country.toUpperCase();

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: tradesRaw } = await supabase
    .from("trades")
    .select("*, accounts(name, broker)")
    .eq("user_id", user.id)
    .or(`ticker_symbol.eq.${tickerUpper},and(ticker_symbol.is.null,asset_name.eq.${tickerUpper})`)
    .order("traded_at", { ascending: false });

  const allTrades: TradeWithAccount[] = (tradesRaw ?? [])
    .map((t) => {
      const { accounts: acc, ...trade } = t as Trade & {
        accounts: { name: string; broker: string | null } | null;
      };
      return { ...trade, account: acc ?? undefined };
    })
    .filter((t) => (t.country_code ?? "KR") === countryUpper);

  if (!allTrades.length) notFound();

  const assetName = allTrades[0].asset_name;
  const sellTrades = allTrades.filter((t) => t.trade_type === "SELL");
  const winCount = sellTrades.filter((t) => t.result === "SUCCESS").length;
  const totalProfitLoss = sellTrades.reduce(
    (sum, t) => sum + (t.profit_loss ? Number(t.profit_loss) : 0),
    0,
  );

  const stats = {
    totalTrades: allTrades.length,
    sellCount: sellTrades.length,
    winCount,
    totalProfitLoss,
  };

  return (
    <StockDetail
      assetName={assetName}
      ticker={tickerUpper}
      country={countryUpper}
      trades={allTrades}
      stats={stats}
    />
  );
}
