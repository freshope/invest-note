-- exchange NULL → 빈 문자열 백필 후 NOT NULL 제약 추가
DO $$
BEGIN
  -- 실제로 NULL 행이 있으면 백필 후 제약 추가; 없으면 no-op
  UPDATE trades SET exchange = '' WHERE exchange IS NULL;
  ALTER TABLE trades ALTER COLUMN exchange SET NOT NULL;
END $$;
