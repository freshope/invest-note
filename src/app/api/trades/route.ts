import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { TradeCreateSchema } from "@/lib/api-server/validators";
import { computeTotalHolding, computeFlexibleBreakdown } from "@/lib/holdings";
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

    // SELL 거래의 computed_pnl: 이미 time-ordered allTrades로 WAC 일괄 계산
    // allTrades를 위해 전체 거래 목록을 ascending으로 재조회 (ticker 필터 없는 경우만)
    let allTradesForPnl: Trade[] = [];
    if (!tickerRaw) {
      // trades는 이미 현재 사용자 전체 — ascending 정렬로 재사용
      allTradesForPnl = [...trades].sort(
        (a, b) => new Date(a.traded_at).getTime() - new Date(b.traded_at).getTime(),
      ) as Trade[];
    } else {
      // ticker 필터 케이스: 정확한 WAC 계산을 위해 전체 거래 별도 조회
      const { data: allRaw } = await supabase
        .from("trades")
        .select("trade_type, quantity, price, ticker_symbol, asset_name, country_code, account_id, traded_at, commission, tax, profit_loss, id")
        .eq("user_id", user.id)
        .order("traded_at", { ascending: true });
      allTradesForPnl = (allRaw ?? []) as Trade[];
    }

    const tradesWithPnl = trades.map((t) => {
      if (t.trade_type !== "SELL") return t;
      const breakdown = computeFlexibleBreakdown(t as Trade, allTradesForPnl);
      return { ...t, computed_pnl: breakdown.pnl };
    });

    const { data: accountsRaw } = await supabase
      .from("accounts")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: true });

    return NextResponse.json({ trades: tradesWithPnl, accounts: accountsRaw ?? [] });
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

    if (fields.trade_type === "SELL") {
      const { data: existingTrades, error: tradesErr } = await supabase
        .from("trades")
        .select("trade_type, quantity, ticker_symbol, asset_name, country_code, account_id, traded_at")
        .eq("user_id", user.id);

      if (tradesErr) return jsonError("보유 수량을 확인할 수 없습니다.", 500);

      const holding = computeTotalHolding((existingTrades ?? []) as Trade[], {
        ticker: fields.ticker_symbol ?? null,
        assetName: fields.asset_name,
        country: fields.country_code ?? "KR",
        accountId: account_id,
      });

      if (holding <= 0) {
        return jsonError("보유하지 않은 종목입니다.", 400);
      }
      if (fields.quantity > holding) {
        return jsonError(`보유 수량이 부족합니다 (현재 ${holding}주).`, 400);
      }
    }

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
