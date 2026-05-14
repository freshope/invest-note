-- trades 테이블에 country_code 컬럼 추가
-- 국내(KR) / 해외(US) / 기타(OTHER) 구분을 위해 추가
ALTER TABLE trades
  ADD COLUMN country_code TEXT NOT NULL DEFAULT 'KR';

-- 기존 데이터는 기본값 'KR'로 자동 설정됨
