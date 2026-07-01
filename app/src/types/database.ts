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
  // 계좌번호(내역서→계좌 매칭용). 저장은 raw 원문, 정규화/동일성 비교는 FE-side.
  account_number: string | null;
  cash_balance: number;
  created_at: string;
  updated_at: string;
  trade_count?: number;
}

export interface Trade {
  id: string;
  user_id: string;
  account_id: string;

  // 거래 기본 정보
  asset_name: string;
  // 종목 마스터(stocks)에서 조회 시점에 채워지는 표시용 한글명(US 영문 asset_name 보완).
  // 응답 전용 — 저장/계산 키는 asset_name. 표시는 name_ko ?? asset_name.
  name_ko?: string | null;
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
  custom_tags: string[];
  buy_reason: string | null;
  sell_reason: string | null;

  // 감정
  emotion: EmotionType | null;

  // 결과
  result: TradeResult | null;

  // 손익 (SELL 전용 — 서버 계산 저장값)
  profit_loss: number | null;
  avg_buy_price: number | null;
  holding_days: number | null;

  // 국가 코드 (KR / US / OTHER)
  country_code: string;

  // 거래소 (KOSPI / KOSDAQ / NYSE / NASDAQ 등, 미상은 빈 문자열)
  exchange: string;

  // 거래 시점 환율(native→KRW). KR=1. KRW 금액 = native × exchange_rate.
  // optional: 구버전 응답/테스트 fixture 호환 — 소비처는 `?? 1` 로 폴백.
  exchange_rate?: number;

  // 수수료 / 제세금
  commission: number;
  tax: number;

  // 거래 출처 — MANUAL(개별등록) / IMPORT(거래내역서 일괄등록). INSERT 시 확정·불변.
  origin: "MANUAL" | "IMPORT";

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
