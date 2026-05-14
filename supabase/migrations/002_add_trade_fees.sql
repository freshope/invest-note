-- 수수료 및 제세금 컬럼 추가
ALTER TABLE trades
  ADD COLUMN commission numeric(18, 2) NOT NULL DEFAULT 0,
  ADD COLUMN tax        numeric(18, 2) NOT NULL DEFAULT 0;
