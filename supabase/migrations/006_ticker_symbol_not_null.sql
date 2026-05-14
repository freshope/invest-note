-- ticker_symbol NULL → asset_name 백필 후 NOT NULL 제약 추가
-- 자동완성 없이 직접 입력한 과거 거래의 ticker_symbol을 asset_name으로 통일
UPDATE trades SET ticker_symbol = asset_name WHERE ticker_symbol IS NULL;

ALTER TABLE trades ALTER COLUMN ticker_symbol SET NOT NULL;
