import { NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { HttpError } from "@/lib/api-server/errors";
import { buildPositions, mergeQuotes, buildAccountSnapshots, buildTotals } from "@/lib/portfolio";
import { fetchQuotesByKeys } from "@/lib/quotes";
import type { Trade, Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

export async function GET() {
  try {
    const { supabase, user } = await requireUser();

    const [{ data: tradesRaw }, { data: accountsRaw }] = await Promise.all([
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

    const trades: TradeWithAccount[] = (tradesRaw ?? []).map((t) => {
      const { accounts: acc, ...trade } = t as Trade & {
        accounts: { name: string; broker: string | null } | null;
      };
      return { ...trade, account: acc ?? undefined };
    });
    const accounts: Account[] = (accountsRaw ?? []) as Account[];

    const positions0 = buildPositions(trades);
    const quotes = await fetchQuotesByKeys(positions0.map((p) => p.key));
    const positions = mergeQuotes(positions0, quotes);
    const snapshots = buildAccountSnapshots(accounts, trades, quotes);
    const totals = buildTotals(positions, accounts, trades);

    return NextResponse.json({
      totals,
      positions,
      snapshots,
      hasAccounts: accounts.length > 0,
      hasTrades: trades.length > 0,
    });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return NextResponse.json({ error: "서버 오류가 발생했습니다." }, { status: 500 });
  }
}
