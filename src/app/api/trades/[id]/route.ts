import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import type {
  Trade,
  TradeType,
  MarketType,
  StrategyType,
  ReasoningTag,
  EmotionType,
  TradeResult,
} from "@/types/database";

const VALID_TRADE_TYPES: TradeType[] = ["BUY", "SELL"];
const VALID_MARKET_TYPES: MarketType[] = ["STOCK", "CRYPTO", "ETC"];
const VALID_COUNTRY_CODES = ["KR", "US", "OTHER"] as const;
type CountryCode = (typeof VALID_COUNTRY_CODES)[number];
const VALID_STRATEGIES: StrategyType[] = ["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"];
const VALID_EMOTIONS: EmotionType[] = ["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"];
const VALID_REASONING_TAGS: ReasoningTag[] = ["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"];
const VALID_RESULTS: TradeResult[] = ["SUCCESS", "FAIL", "BREAKEVEN"];

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

function parseNumber(raw: unknown): number | null {
  if (raw == null || raw === "") return null;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num)) return null;
  return num;
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const { data, error } = await supabase
      .from("trades")
      .select("*, accounts(name, broker)")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (error || !data) return jsonError("거래를 찾을 수 없습니다.", 404);

    const { accounts: acc, ...trade } = data as Trade & {
      accounts: { name: string; broker: string | null } | null;
    };
    return NextResponse.json({ ...trade, account: acc ?? undefined });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;
    const body = await req.json();

    // 소유 확인
    const { data: existing, error: fetchError } = await supabase
      .from("trades")
      .select("id, trade_type")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (fetchError || !existing) return jsonError("거래를 찾을 수 없습니다.", 404);

    // 업데이트할 필드만 추려서 patch 구성
    const patch: Record<string, unknown> = {};

    // 기본 필드
    if (body.trade_type !== undefined) {
      if (!VALID_TRADE_TYPES.includes(body.trade_type))
        return jsonError("올바른 거래 유형을 선택해주세요.", 400);
      patch.trade_type = body.trade_type;
    }
    if (body.market_type !== undefined) {
      if (!VALID_MARKET_TYPES.includes(body.market_type))
        return jsonError("올바른 시장 유형을 선택해주세요.", 400);
      patch.market_type = body.market_type;
    }
    if (body.account_id !== undefined) {
      const accountId = String(body.account_id).trim();
      const { count } = await supabase
        .from("accounts")
        .select("id", { count: "exact", head: true })
        .eq("id", accountId)
        .eq("user_id", user.id);
      if (!count) return jsonError("올바른 계좌를 선택해주세요.", 400);
      patch.account_id = accountId;
    }
    if (body.asset_name !== undefined) {
      const assetName = String(body.asset_name).trim();
      if (!assetName) return jsonError("종목명을 입력해주세요.", 400);
      if (assetName.length > 100) return jsonError("종목명은 100자 이하로 입력해주세요.", 400);
      patch.asset_name = assetName;
    }
    if (body.ticker_symbol !== undefined) {
      patch.ticker_symbol = body.ticker_symbol ? String(body.ticker_symbol).trim() : null;
    }
    if (body.country_code !== undefined) {
      const cc = String(body.country_code).trim();
      patch.country_code = VALID_COUNTRY_CODES.includes(cc as CountryCode) ? cc : "KR";
    }
    if (body.traded_at !== undefined) {
      if (!body.traded_at) return jsonError("날짜를 선택해주세요.", 400);
      patch.traded_at = new Date(body.traded_at).toISOString();
    }
    if (body.price !== undefined) {
      const price = parsePositiveNumber(body.price);
      if (price === null) return jsonError("올바른 가격을 입력해주세요.", 400);
      patch.price = price;
    }
    if (body.quantity !== undefined) {
      const quantity = parsePositiveNumber(body.quantity);
      if (quantity === null) return jsonError("올바른 수량을 입력해주세요.", 400);
      patch.quantity = quantity;
    }
    if (body.commission !== undefined) {
      const commission = parseNonNegativeNumber(body.commission);
      if (commission === null) return jsonError("올바른 수수료를 입력해주세요.", 400);
      patch.commission = commission;
    }
    if (body.tax !== undefined) {
      const tax = parseNonNegativeNumber(body.tax);
      if (tax === null) return jsonError("올바른 제세금을 입력해주세요.", 400);
      patch.tax = tax;
    }

    // 메타 필드
    if ("strategy_type" in body) {
      patch.strategy_type =
        body.strategy_type && VALID_STRATEGIES.includes(body.strategy_type)
          ? body.strategy_type
          : null;
    }
    if ("emotion" in body) {
      patch.emotion =
        body.emotion && VALID_EMOTIONS.includes(body.emotion) ? body.emotion : null;
    }
    if ("reasoning_tags" in body) {
      patch.reasoning_tags = Array.isArray(body.reasoning_tags)
        ? body.reasoning_tags.filter((t: string) =>
            VALID_REASONING_TAGS.includes(t as ReasoningTag)
          )
        : [];
    }
    if ("buy_reason" in body) patch.buy_reason = body.buy_reason ?? null;
    if ("sell_reason" in body) patch.sell_reason = body.sell_reason ?? null;
    if ("result" in body) {
      patch.result =
        body.result && VALID_RESULTS.includes(body.result) ? body.result : null;
    }
    if ("profit_loss" in body) patch.profit_loss = parseNumber(body.profit_loss);
    if ("reflection_note" in body) patch.reflection_note = body.reflection_note ?? null;
    if ("improvement_note" in body) patch.improvement_note = body.improvement_note ?? null;

    if (Object.keys(patch).length === 0) return new NextResponse(null, { status: 204 });

    const { error } = await supabase
      .from("trades")
      .update(patch)
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) return jsonError("저장할 수 없습니다. 다시 시도해주세요.", 500);
    return new NextResponse(null, { status: 204 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const { error } = await supabase
      .from("trades")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) return jsonError("삭제할 수 없습니다. 다시 시도해주세요.", 500);
    return new NextResponse(null, { status: 204 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
