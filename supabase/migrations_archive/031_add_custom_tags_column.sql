-- trades 테이블에 사용자 정의 분석 태그(custom_tags) 컬럼 추가
-- 고정 ENUM 인 reasoning_tags 와 달리, 사용자가 자유 텍스트로 직접 만드는 분류 태그.
-- BUY 에 입력 → SELL 에 매칭 최신 BUY 기준 자동 상속(pnl_sync) → 분석 탭 태그별 집계.
-- 신규 컬럼이라 backfill 불필요(빈 배열로 시작). reasoning_tag[] 와 평행 구조.
ALTER TABLE trades
  ADD COLUMN custom_tags text[] NOT NULL DEFAULT '{}';
