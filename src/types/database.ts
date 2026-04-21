// ============================================================
// Enum 타입
// ============================================================

export type MarketType = 'STOCK' | 'CRYPTO' | 'ETC';
export type TradeType = 'BUY' | 'SELL';
export type StrategyType = 'SCALPING' | 'SWING' | 'LONG_TERM' | 'UNKNOWN';
export type ReasoningTag = 'TECHNICAL' | 'FUNDAMENTAL' | 'NEWS' | 'FEELING';
export type EmotionType = 'CONFIDENT' | 'ANXIOUS' | 'FOMO' | 'IMPULSIVE' | 'CALM';
export type TradeResult = 'SUCCESS' | 'FAIL' | 'BREAKEVEN';

// ============================================================
// 테이블 Row 타입
// ============================================================

export interface Account {
  id: string;
  user_id: string;
  name: string;
  broker: string | null;
  cash_balance: number;
  created_at: string;
  updated_at: string;
}

export interface Trade {
  id: string;
  user_id: string;
  account_id: string;

  // 거래 기본 정보
  asset_name: string;
  ticker_symbol: string;
  market_type: MarketType;
  trade_type: TradeType;
  price: number;
  quantity: number;
  total_amount: number; // generated column
  traded_at: string;

  // 근거
  strategy_type: StrategyType | null;
  reasoning_tags: ReasoningTag[];
  buy_reason: string | null;
  sell_reason: string | null;

  // 감정
  emotion: EmotionType | null;

  // 회고
  result: TradeResult | null;
  reflection_note: string | null;
  improvement_note: string | null;

  // 손익 (SELL 전용 — 서버 계산 저장값)
  profit_loss: number | null;
  avg_buy_price: number | null;

  // 국가 코드 (KR / US / OTHER)
  country_code: string;

  // 거래소 (KOSPI / KOSDAQ / NYSE / NASDAQ 등)
  exchange?: string | null;

  // 수수료 / 제세금
  commission: number;
  tax: number;

  created_at: string;
  updated_at: string;
}

// ============================================================
// Insert / Update 타입 (생성 컬럼 제외)
// ============================================================

export type AccountInsert = Omit<Account, 'id' | 'created_at' | 'updated_at'>;
export type AccountUpdate = Partial<Omit<Account, 'id' | 'user_id' | 'created_at' | 'updated_at'>>;

export type TradeInsert = Omit<Trade, 'id' | 'total_amount' | 'created_at' | 'updated_at'>;
export type TradeUpdate = Partial<Omit<Trade, 'id' | 'user_id' | 'total_amount' | 'created_at' | 'updated_at'>>;

// ============================================================
// Supabase Database 타입 (클라이언트용)
// ============================================================

export interface Database {
  public: {
    Tables: {
      accounts: {
        Row: Account;
        Insert: AccountInsert;
        Update: AccountUpdate;
      };
      trades: {
        Row: Trade;
        Insert: TradeInsert;
        Update: TradeUpdate;
      };
    };
    Enums: {
      market_type: MarketType;
      trade_type: TradeType;
      strategy_type: StrategyType;
      reasoning_tag: ReasoningTag;
      emotion_type: EmotionType;
      trade_result: TradeResult;
    };
  };
}
