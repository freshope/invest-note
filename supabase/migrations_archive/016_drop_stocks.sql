-- stocks 마스터 제거: 일괄 등록 종목명→ticker 매칭을 Naver 검색 API 단일 경로로 단일화.
-- 마스터 데이터를 자체 시드(KIND)로 유지하던 구조는 ETF/ETN/약칭을 커버하지 못해 폐기.
-- 014/015 마이그레이션은 역사 기록으로 보존하고, 본 마이그레이션에서 테이블만 drop 한다.
-- trades 테이블은 stocks 를 FK 로 참조하지 않아 거래 데이터에는 영향 없다.
-- 자세한 결정 배경은 docs/decisions.md 참고.

drop table if exists public.stocks;
