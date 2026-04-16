-- 종목코드 컬럼 추가 (nullable: 검색 외 직접 입력 종목 허용)
ALTER TABLE trades ADD COLUMN ticker_symbol text;
