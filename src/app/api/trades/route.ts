import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { TradeCreateSchema } from "@/lib/api-server/validators";
import type { Trade } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

export async function GET(req: NextRequest) {
  try {
    const { supabase, user } = await requireUser();
    const { searchParams } = req.nextUrl;
    const tickerRaw = searchParams.get("ticker");
    const country = searchParams.get("country") ?? "KR";

    let query = supabase
      .from("trades")
      .select("*, accounts(name, broker)")
      .eq("user_id", user.id)
      .order("traded_at", { ascending: false });

    if (tickerRaw) {
      const ticker = tickerRaw.slice(0, 30);
      if (!/^[A-Za-z0-9.\-_가-힣]+$/.test(ticker)) {
        return jsonError("invalid ticker", 400);
      }
      const t = encodeURIComponent(ticker);
      query = query.or(
        `ticker_symbol.eq.${t},and(ticker_symbol.is.null,asset_name.eq.${t})`
      );
    }

    const { data: tradesRaw, error } = await query;
    if (error) return jsonError("거래 목록을 불러올 수 없습니다.", 500);

    let trades: TradeWithAccount[] = (tradesRaw ?? []).map((t) => {
      const { accounts: acc, ...trade } = t as Trade & {
        accounts: { name: string; broker: string | null } | null;
      };
      return { ...trade, account: acc ?? undefined };
    });

    if (tickerRaw) {
      trades = trades.filter((t) => (t.country_code ?? "KR") === country);
    }

    const { data: accountsRaw } = await supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: true });

    return NextResponse.json({ trades, accounts: accountsRaw ?? [] });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}

export async function POST(req: NextRequest) {
  try {
    const { supabase, user } = await requireUser();

    const parsed = TradeCreateSchema.safeParse(await req.json());
    if (!parsed.success) {
      return jsonError(parsed.error.issues[0]?.message ?? "올바르지 않은 입력입니다.", 400);
    }

    const { account_id, ...fields } = parsed.data;

    const { count, error: acctError } = await supabase
      .from("accounts")
      .select("id", { count: "exact", head: true })
      .eq("id", account_id)
      .eq("user_id", user.id);

    if (acctError || !count) return jsonError("올바른 계좌를 선택해주세요.", 400);

    const { data, error } = await supabase
      .from("trades")
      .insert({ user_id: user.id, account_id, ...fields })
      .select("id, trade_type")
      .single();

    if (error || !data) return jsonError("거래를 저장할 수 없습니다. 다시 시도해주세요.", 500);
    return NextResponse.json(data, { status: 201 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
