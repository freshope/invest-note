import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { Trade, Account } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

export async function GET(request: NextRequest) {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();
  if (authError || !user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const tickerRaw = request.nextUrl.searchParams.get("ticker");
  const country = request.nextUrl.searchParams.get("country") ?? "KR";
  if (!tickerRaw) return NextResponse.json({ error: "ticker required" }, { status: 400 });

  // 허용 문자: 영문·숫자·점·하이픈·밑줄, 최대 30자
  const ticker = tickerRaw.slice(0, 30);
  if (!/^[A-Za-z0-9.\-_]+$/.test(ticker)) {
    return NextResponse.json({ error: "invalid ticker" }, { status: 400 });
  }

  const [{ data: tradesRaw }, { data: accountsRaw }] = await Promise.all([
    supabase
      .from("trades")
      .select("*, accounts(name, broker)")
      .eq("user_id", user.id)
      // ticker_symbol 일치 또는 (ticker_symbol 없고 asset_name 일치)
      .or(`ticker_symbol.eq.${ticker},and(ticker_symbol.is.null,asset_name.eq.${ticker})`)
      .order("traded_at", { ascending: false }),
    supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id),
  ]);

  const allTrades: TradeWithAccount[] = (tradesRaw ?? []).map((t) => {
    const { accounts: acc, ...trade } = t as Trade & {
      accounts: { name: string; broker: string | null } | null;
    };
    return { ...trade, account: acc ?? undefined };
  });

  // country_code가 null이면 기본 KR로 처리
  const trades = allTrades.filter((t) => (t.country_code ?? "KR") === country);
  const accounts: Account[] = (accountsRaw ?? []) as Account[];

  return NextResponse.json({ trades, accounts });
}
