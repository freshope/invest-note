"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { TradeType, MarketType, StrategyType, ReasoningTag, EmotionType, TradeResult } from "@/types/database";

export type TradeActionState =
  | { error: string }
  | { success: true; tradeId: string; tradeType: TradeType }
  | undefined;

export type MetaActionState =
  | { error: string }
  | { success: true }
  | undefined;

const VALID_TRADE_TYPES: TradeType[] = ["BUY", "SELL"];
const VALID_COUNTRY_CODES = ["KR", "US", "OTHER"] as const;
type CountryCode = typeof VALID_COUNTRY_CODES[number];
const VALID_MARKET_TYPES: MarketType[] = ["STOCK", "CRYPTO", "ETC"];
const VALID_STRATEGIES: StrategyType[] = ["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"];
const VALID_EMOTIONS: EmotionType[] = ["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"];
const VALID_REASONING_TAGS: ReasoningTag[] = ["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"];
const VALID_RESULTS: TradeResult[] = ["SUCCESS", "FAIL", "BREAKEVEN"];

function parsePositiveNumber(raw: string | null): number | null {
  if (!raw || raw.trim() === "") return null;
  const num = Number(raw.replace(/,/g, ""));
  if (isNaN(num) || num <= 0) return null;
  return num;
}

function parseNonNegativeNumber(raw: string | null): number | null {
  if (!raw || raw.trim() === "") return 0;
  const num = Number(raw.replace(/,/g, ""));
  if (isNaN(num) || num < 0) return null;
  return num;
}

function parseNumber(raw: string | null): number | null {
  if (!raw || raw.trim() === "") return null;
  const num = Number(raw.replace(/,/g, ""));
  if (isNaN(num)) return null;
  return num;
}

export async function createTrade(
  _state: TradeActionState,
  formData: FormData
): Promise<TradeActionState> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return { error: "로그인이 필요합니다." };
  }

  const tradeTypeRaw = formData.get("trade_type") as string;
  const marketTypeRaw = (formData.get("market_type") as string) || "STOCK";
  const accountId = (formData.get("account_id") as string)?.trim();
  const assetName = (formData.get("asset_name") as string)?.trim();
  const tickerSymbol = (formData.get("ticker_symbol") as string)?.trim() || null;
  const countryCodeRaw = (formData.get("country_code") as string)?.trim();
  const countryCode: CountryCode = VALID_COUNTRY_CODES.includes(countryCodeRaw as CountryCode)
    ? (countryCodeRaw as CountryCode)
    : "KR";
  const tradedAt = (formData.get("traded_at") as string)?.trim();

  const priceRaw = formData.get("price") as string;
  const quantityRaw = formData.get("quantity") as string;
  const commissionRaw = formData.get("commission") as string;
  const taxRaw = formData.get("tax") as string;

  // 유효성 검사
  if (!VALID_TRADE_TYPES.includes(tradeTypeRaw as TradeType)) {
    return { error: "올바른 거래 유형을 선택해주세요." };
  }
  if (!VALID_MARKET_TYPES.includes(marketTypeRaw as MarketType)) {
    return { error: "올바른 시장 유형을 선택해주세요." };
  }
  if (!accountId) return { error: "계좌를 선택해주세요." };
  if (!assetName) return { error: "종목명을 입력해주세요." };
  if (assetName.length > 100) return { error: "종목명은 100자 이하로 입력해주세요." };
  if (!tradedAt) return { error: "날짜를 선택해주세요." };

  const price = parsePositiveNumber(priceRaw);
  if (price === null) return { error: "올바른 가격을 입력해주세요." };

  const quantity = parsePositiveNumber(quantityRaw);
  if (quantity === null) return { error: "올바른 수량을 입력해주세요." };

  const commission = parseNonNegativeNumber(commissionRaw);
  if (commission === null) return { error: "올바른 수수료를 입력해주세요." };

  const tax = parseNonNegativeNumber(taxRaw);
  if (tax === null) return { error: "올바른 제세금을 입력해주세요." };

  // 계좌가 사용자 소유인지 확인
  const { count, error: acctError } = await supabase
    .from("accounts")
    .select("id", { count: "exact", head: true })
    .eq("id", accountId)
    .eq("user_id", user.id);

  if (acctError || !count) {
    return { error: "올바른 계좌를 선택해주세요." };
  }

  const { data, error } = await supabase
    .from("trades")
    .insert({
      user_id: user.id,
      account_id: accountId,
      asset_name: assetName,
      ticker_symbol: tickerSymbol,
      country_code: countryCode,
      market_type: marketTypeRaw as MarketType,
      trade_type: tradeTypeRaw as TradeType,
      price,
      quantity,
      commission,
      tax,
      traded_at: new Date(tradedAt).toISOString(),
    })
    .select("id, trade_type")
    .single();

  if (error || !data) {
    return { error: "거래를 저장할 수 없습니다. 다시 시도해주세요." };
  }

  revalidatePath("/records");
  return { success: true, tradeId: data.id, tradeType: data.trade_type as TradeType };
}

export async function updateTradeMetadata(
  _state: MetaActionState,
  formData: FormData
): Promise<MetaActionState> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return { error: "로그인이 필요합니다." };
  }

  const id = (formData.get("id") as string)?.trim();
  if (!id) return { error: "거래 정보가 올바르지 않습니다." };

  // 거래 소유자 확인
  const { data: trade, error: fetchError } = await supabase
    .from("trades")
    .select("id, trade_type")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  if (fetchError || !trade) {
    return { error: "거래를 찾을 수 없습니다." };
  }

  const strategyRaw = formData.get("strategy_type") as string;
  const emotionRaw = formData.get("emotion") as string;
  const reasoningTagsRaw = formData.get("reasoning_tags") as string;
  const buyReason = (formData.get("buy_reason") as string)?.trim() || null;
  const sellReason = (formData.get("sell_reason") as string)?.trim() || null;
  const resultRaw = formData.get("result") as string;
  const profitLossRaw = formData.get("profit_loss") as string;
  const reflectionNote = (formData.get("reflection_note") as string)?.trim() || null;
  const improvementNote = (formData.get("improvement_note") as string)?.trim() || null;

  const strategy = strategyRaw && VALID_STRATEGIES.includes(strategyRaw as StrategyType)
    ? (strategyRaw as StrategyType)
    : null;

  const emotion = emotionRaw && VALID_EMOTIONS.includes(emotionRaw as EmotionType)
    ? (emotionRaw as EmotionType)
    : null;

  const reasoningTags: ReasoningTag[] = reasoningTagsRaw
    ? reasoningTagsRaw.split(",").filter(t => VALID_REASONING_TAGS.includes(t as ReasoningTag)) as ReasoningTag[]
    : [];

  const result = resultRaw && VALID_RESULTS.includes(resultRaw as TradeResult)
    ? (resultRaw as TradeResult)
    : null;

  const profitLoss = profitLossRaw ? parseNumber(profitLossRaw) : null;

  const { error } = await supabase
    .from("trades")
    .update({
      strategy_type: strategy,
      emotion,
      reasoning_tags: reasoningTags,
      buy_reason: buyReason,
      sell_reason: sellReason,
      result,
      profit_loss: profitLoss,
      reflection_note: reflectionNote,
      improvement_note: improvementNote,
    })
    .eq("id", id)
    .eq("user_id", user.id);

  if (error) {
    return { error: "저장할 수 없습니다. 다시 시도해주세요." };
  }

  revalidatePath("/records");
  return { success: true };
}

export type UpdateTradeActionState =
  | { error: string }
  | { success: true }
  | undefined;

export async function updateTrade(
  _state: UpdateTradeActionState,
  formData: FormData
): Promise<UpdateTradeActionState> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return { error: "로그인이 필요합니다." };
  }

  const id = (formData.get("id") as string)?.trim();
  if (!id) return { error: "거래 정보가 올바르지 않습니다." };

  // 소유자 확인
  const { data: existing, error: fetchError } = await supabase
    .from("trades")
    .select("id")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  if (fetchError || !existing) {
    return { error: "거래를 찾을 수 없습니다." };
  }

  const tradeTypeRaw = formData.get("trade_type") as string;
  const marketTypeRaw = (formData.get("market_type") as string) || "STOCK";
  const accountId = (formData.get("account_id") as string)?.trim();
  const assetName = (formData.get("asset_name") as string)?.trim();
  const tickerSymbol = (formData.get("ticker_symbol") as string)?.trim() || null;
  const countryCodeRaw = (formData.get("country_code") as string)?.trim();
  const countryCode: CountryCode = VALID_COUNTRY_CODES.includes(countryCodeRaw as CountryCode)
    ? (countryCodeRaw as CountryCode)
    : "KR";
  const tradedAt = (formData.get("traded_at") as string)?.trim();

  const priceRaw = formData.get("price") as string;
  const quantityRaw = formData.get("quantity") as string;
  const commissionRaw = formData.get("commission") as string;
  const taxRaw = formData.get("tax") as string;

  if (!VALID_TRADE_TYPES.includes(tradeTypeRaw as TradeType)) {
    return { error: "올바른 거래 유형을 선택해주세요." };
  }
  if (!VALID_MARKET_TYPES.includes(marketTypeRaw as MarketType)) {
    return { error: "올바른 시장 유형을 선택해주세요." };
  }
  if (!accountId) return { error: "계좌를 선택해주세요." };
  if (!assetName) return { error: "종목명을 입력해주세요." };
  if (assetName.length > 100) return { error: "종목명은 100자 이하로 입력해주세요." };
  if (!tradedAt) return { error: "날짜를 선택해주세요." };

  const price = parsePositiveNumber(priceRaw);
  if (price === null) return { error: "올바른 가격을 입력해주세요." };

  const quantity = parsePositiveNumber(quantityRaw);
  if (quantity === null) return { error: "올바른 수량을 입력해주세요." };

  const commission = parseNonNegativeNumber(commissionRaw);
  if (commission === null) return { error: "올바른 수수료를 입력해주세요." };

  const tax = parseNonNegativeNumber(taxRaw);
  if (tax === null) return { error: "올바른 제세금을 입력해주세요." };

  // 계좌 소유자 확인
  const { count, error: acctError } = await supabase
    .from("accounts")
    .select("id", { count: "exact", head: true })
    .eq("id", accountId)
    .eq("user_id", user.id);

  if (acctError || !count) {
    return { error: "올바른 계좌를 선택해주세요." };
  }

  // 메타 필드
  const strategyRaw = formData.get("strategy_type") as string;
  const emotionRaw = formData.get("emotion") as string;
  const reasoningTagsRaw = formData.get("reasoning_tags") as string;
  const buyReason = (formData.get("buy_reason") as string)?.trim() || null;
  const sellReason = (formData.get("sell_reason") as string)?.trim() || null;
  const resultRaw = formData.get("result") as string;
  const profitLossRaw = formData.get("profit_loss") as string;
  const reflectionNote = (formData.get("reflection_note") as string)?.trim() || null;
  const improvementNote = (formData.get("improvement_note") as string)?.trim() || null;

  const strategy = strategyRaw && VALID_STRATEGIES.includes(strategyRaw as StrategyType)
    ? (strategyRaw as StrategyType)
    : null;

  const emotion = emotionRaw && VALID_EMOTIONS.includes(emotionRaw as EmotionType)
    ? (emotionRaw as EmotionType)
    : null;

  const reasoningTags: ReasoningTag[] = reasoningTagsRaw
    ? reasoningTagsRaw.split(",").filter(t => VALID_REASONING_TAGS.includes(t as ReasoningTag)) as ReasoningTag[]
    : [];

  const result = resultRaw && VALID_RESULTS.includes(resultRaw as TradeResult)
    ? (resultRaw as TradeResult)
    : null;

  const profitLoss = profitLossRaw ? parseNumber(profitLossRaw) : null;

  const { error } = await supabase
    .from("trades")
    .update({
      account_id: accountId,
      asset_name: assetName,
      ticker_symbol: tickerSymbol,
      country_code: countryCode,
      market_type: marketTypeRaw as MarketType,
      trade_type: tradeTypeRaw as TradeType,
      price,
      quantity,
      commission,
      tax,
      traded_at: new Date(tradedAt).toISOString(),
      strategy_type: strategy,
      emotion,
      reasoning_tags: reasoningTags,
      buy_reason: buyReason,
      sell_reason: sellReason,
      result,
      profit_loss: profitLoss,
      reflection_note: reflectionNote,
      improvement_note: improvementNote,
    })
    .eq("id", id)
    .eq("user_id", user.id);

  if (error) {
    return { error: "저장할 수 없습니다. 다시 시도해주세요." };
  }

  revalidatePath(`/records/${id}`);
  revalidatePath("/records");
  return { success: true };
}

export async function deleteTrade(id: string): Promise<{ error?: string }> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) return { error: "로그인이 필요합니다." };

  const { error } = await supabase
    .from("trades")
    .delete()
    .eq("id", id)
    .eq("user_id", user.id);

  if (error) return { error: "삭제할 수 없습니다. 다시 시도해주세요." };

  revalidatePath("/records");
  return {};
}
