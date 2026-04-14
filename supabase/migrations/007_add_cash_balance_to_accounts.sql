-- 계좌 예수금(현금 잔고) 수동 입력 지원
-- v2에서 KIS API 자동 조회로 대체 예정

ALTER TABLE accounts
  ADD COLUMN IF NOT EXISTS cash_balance NUMERIC(15,2) NOT NULL DEFAULT 0
    CONSTRAINT accounts_cash_balance_non_negative CHECK (cash_balance >= 0),
  ADD COLUMN IF NOT EXISTS cash_balance_updated_at TIMESTAMPTZ;
