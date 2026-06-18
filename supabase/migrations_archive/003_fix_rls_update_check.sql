-- UPDATE 정책에 WITH CHECK 추가 (user_id 변조 방지)
-- USING: 수정 대상 행 필터 (수정 전 상태)
-- WITH CHECK: 수정 결과 행 검증 (수정 후 상태)
ALTER POLICY "accounts: 본인만 수정" ON accounts
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER POLICY "trades: 본인만 수정" ON trades
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
