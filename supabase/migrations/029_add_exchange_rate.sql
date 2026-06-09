-- trades 테이블에 거래 시점 환율(exchange_rate) 컬럼 추가
-- 해외 거래의 원화 환산 기준값을 거래 시점에 고정 저장한다(매입원가·실현손익을 그 시점 원화로 확정).
-- 국내(KR) 거래는 1.0. KRW 환산값 = native 금액(price/commission/tax) × exchange_rate.
ALTER TABLE trades
  ADD COLUMN exchange_rate numeric(18, 6) NOT NULL DEFAULT 1;

-- 기존 데이터는 기본값 1.0 으로 백필됨(KR 은 정답, 기존 US 거래는 부정확 → 재등록 필요).
