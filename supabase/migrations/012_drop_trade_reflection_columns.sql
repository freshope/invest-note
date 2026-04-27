-- 매도 거래의 잘한점/개선할점 자유 텍스트 컬럼 제거
-- 010에서 추가한 length CHECK 제약은 컬럼 DROP 시 Postgres가 자동으로 cascade 정리
ALTER TABLE trades
  DROP COLUMN IF EXISTS reflection_note,
  DROP COLUMN IF EXISTS improvement_note;
