import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import type { Trade, TradeType, MarketType } from "@/types/database";
import type { TradeWithAccount } from "@/lib/trade-utils";

const VALID_TRADE_TYPES: TradeType[] = ["BUY", "SELL"];
const VALID_MARKET_TYPES: MarketType[] = ["STOCK", "CRYPTO", "ETC"];
const VALID_COUNTRY_CODES = ["KR", "US", "OTHER"] as const;
type CountryCode = (typeof VALID_COUNTRY_CODES)[number];

function parsePositiveNumber(raw: unknown): number | null {
  if (raw == null || raw === "") return null;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num) || num <= 0) return null;
  return num;
}

function parseNonNegativeNumber(raw: unknown): number | null {
  if (raw == null || raw === "") return 0;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num) || num < 0) return null;
  return num;
}

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
      // ticker_symbol 일치 또는 (ticker_symbol 없고 asset_name 일치)
      query = query.or(
        `ticker_symbol.eq.${ticker},and(ticker_symbol.is.null,asset_name.eq.${ticker})`
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
    const body = await req.json();

    const tradeType = body.trade_type as string;
    const marketType = (body.market_type as string) || "STOCK";
    const accountId = String(body.account_id ?? "").trim();
    const assetName = String(body.asset_name ?? "").trim();
    const tickerSymbol = body.ticker_symbol ? String(body.ticker_symbol).trim() : null;
    const countryCodeRaw = String(body.country_code ?? "KR").trim();
    const countryCode: CountryCode = VALID_COUNTRY_CODES.includes(countryCodeRaw as CountryCode)
      ? (countryCodeRaw as CountryCode)
      : "KR";
    const tradedAt = String(body.traded_at ?? "").trim();

    if (!VALID_TRADE_TYPES.includes(tradeType as TradeType))
      return jsonError("올바른 거래 유형을 선택해주세요.", 400);
    if (!VALID_MARKET_TYPES.includes(marketType as MarketType))
      return jsonError("올바른 시장 유형을 선택해주세요.", 400);
    if (!accountId) return jsonError("계좌를 선택해주세요.", 400);
    if (!assetName) return jsonError("종목명을 입력해주세요.", 400);
    if (assetName.length > 100) return jsonError("종목명은 100자 이하로 입력해주세요.", 400);
    if (!tradedAt) return jsonError("날짜를 선택해주세요.", 400);

    const price = parsePositiveNumber(body.price);
    if (price === null) return jsonError("올바른 가격을 입력해주세요.", 400);

    const quantity = parsePositiveNumber(body.quantity);
    if (quantity === null) return jsonError("올바른 수량을 입력해주세요.", 400);

    const commission = parseNonNegativeNumber(body.commission);
    if (commission === null) return jsonError("올바른 수수료를 입력해주세요.", 400);

    const tax = parseNonNegativeNumber(body.tax);
    if (tax === null) return jsonError("올바른 제세금을 입력해주세요.", 400);

    // 계좌 소유 확인
    const { count, error: acctError } = await supabase
      .from("accounts")
      .select("id", { count: "exact", head: true })
      .eq("id", accountId)
      .eq("user_id", user.id);

    if (acctError || !count) return jsonError("올바른 계좌를 선택해주세요.", 400);

    const { data, error } = await supabase
      .from("trades")
      .insert({
        user_id: user.id,
        account_id: accountId,
        asset_name: assetName,
        ticker_symbol: tickerSymbol,
        country_code: countryCode,
        market_type: marketType as MarketType,
        trade_type: tradeType as TradeType,
        price,
        quantity,
        commission,
        tax,
        traded_at: new Date(tradedAt).toISOString(),
      })
      .select("id, trade_type")
      .single();

    if (error || !data) return jsonError("거래를 저장할 수 없습니다. 다시 시도해주세요.", 500);
    return NextResponse.json(data, { status: 201 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
