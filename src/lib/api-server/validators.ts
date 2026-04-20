import { z } from "zod";
import type { TradeType, MarketType, StrategyType, EmotionType, ReasoningTag, TradeResult } from "@/types/database";

// ============================================================
// Constants (하위 호환)
// ============================================================

export const MAX_NAME_LENGTH = 50;
export const MAX_BROKER_LENGTH = 50;

export const VALID_TRADE_TYPES: TradeType[] = ["BUY", "SELL"];
export const VALID_MARKET_TYPES: MarketType[] = ["STOCK", "CRYPTO", "ETC"];
export const VALID_COUNTRY_CODES = ["KR", "US", "OTHER"] as const;
export type CountryCode = (typeof VALID_COUNTRY_CODES)[number];
export const VALID_STRATEGIES: StrategyType[] = ["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"];
export const VALID_EMOTIONS: EmotionType[] = ["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"];
export const VALID_REASONING_TAGS: ReasoningTag[] = ["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"];
export const VALID_RESULTS: TradeResult[] = ["SUCCESS", "FAIL", "BREAKEVEN"];

// ============================================================
// Primitive helpers
// ============================================================

// zod transform 전용: safeParse-safe 버전
// (주의: transform 내 throw는 zod v4에서 safeParse가 잡지 못하므로 ctx.addIssue 패턴 사용)
const tradedAtTransform = z
  .string()
  .min(1, "날짜를 선택해주세요.")
  .transform((raw, ctx) => {
    const d = new Date(`${raw}+09:00`);
    if (isNaN(d.getTime())) {
      ctx.addIssue({ code: "custom", message: "traded_at: 올바른 날짜/시간 형식이 아닙니다" });
      return z.NEVER;
    }
    return d.toISOString();
  });

// 쉼표 포함 문자열/숫자 → 양수
const commaPositive = z
  .union([z.string(), z.number()])
  .transform((v) => Number(String(v).replace(/,/g, "")))
  .pipe(z.number().positive());

// 쉼표 포함 문자열/숫자 → 0 이상
const commaNonNegative = z
  .union([z.string(), z.number()])
  .transform((v) => Number(String(v).replace(/,/g, "")))
  .pipe(z.number().min(0));

// 쉼표 포함 문자열/숫자 → 임의 숫자(음수 허용)
const commaNumber = z
  .union([z.string(), z.number()])
  .transform((v) => Number(String(v).replace(/,/g, "")))
  .pipe(z.number());

// ============================================================
// Trade PATCH schema
// ============================================================

export const TradeUpdateSchema = z
  .object({
    market_type: z.enum(["STOCK", "CRYPTO", "ETC"]),
    // PATCH 스키마: .default() 사용 금지 — zod v4에서 .partial() + .default() 조합 시
    // 필드가 absent해도 default 값이 materialized되어 patch에 포함됨 → 기존 값 덮어쓰기 버그
    // 수정 불가 필드: trade_type(거래 유형 불변), traded_at(시점 불변),
    //   profit_loss/avg_buy_price(서버 계산 전용),
    //   account_id/ticker_symbol/asset_name/country_code(삭제 후 재등록 정책)
    price: commaPositive,
    quantity: commaPositive,
    commission: commaNonNegative,
    tax: commaNonNegative,
    strategy_type: z.enum(["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"]).nullable(),
    emotion: z.enum(["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]).nullable(),
    reasoning_tags: z.array(z.enum(["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"])),
    buy_reason: z.string().nullable(),
    sell_reason: z.string().nullable(),
    result: z.enum(["SUCCESS", "FAIL", "BREAKEVEN"]).nullable(),
    reflection_note: z.string().nullable(),
    improvement_note: z.string().nullable(),
  })
  .partial();

export type TradeUpdate = z.infer<typeof TradeUpdateSchema>;

// ============================================================
// Trade POST schema
// ============================================================

export const TradeCreateSchema = z.object({
  trade_type: z.enum(["BUY", "SELL"]),
  market_type: z.enum(["STOCK", "CRYPTO", "ETC"]).default("STOCK"),
  account_id: z.string().trim().min(1),
  asset_name: z.string().trim().min(1).max(100),
  ticker_symbol: z.string().trim().min(1),
  country_code: z.enum(["KR", "US", "OTHER"]).default("KR"),
  traded_at: tradedAtTransform,
  price: commaPositive,
  quantity: commaPositive,
  commission: commaNonNegative,
  tax: commaNonNegative,
});

export type TradeCreate = z.infer<typeof TradeCreateSchema>;

// ============================================================
// Account schemas
// ============================================================

const MAX_CASH_BALANCE = 9999999999999999.99;

const cashBalanceField = z
  .union([z.string(), z.number()])
  .transform((v) => (v === "" ? 0 : Number(String(v).replace(/,/g, ""))))
  .pipe(z.number().min(0).max(MAX_CASH_BALANCE));

export const AccountCreateSchema = z.object({
  name: z.string().trim().min(1).max(MAX_NAME_LENGTH),
  broker: z.string().trim().max(MAX_BROKER_LENGTH).nullable().transform((v) => v || null),
  cash_balance: cashBalanceField,
});

export type AccountCreate = z.infer<typeof AccountCreateSchema>;

export const AccountUpdateSchema = z
  .object({
    name: z.string().trim().min(1).max(MAX_NAME_LENGTH),
    broker: z.string().trim().max(MAX_BROKER_LENGTH).nullable().transform((v) => v || null),
    cash_balance: cashBalanceField,
  })
  .partial();

export type AccountUpdate = z.infer<typeof AccountUpdateSchema>;

