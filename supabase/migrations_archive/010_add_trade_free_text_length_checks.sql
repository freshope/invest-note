-- 자유 텍스트 필드 5000자 제한
-- CHECK 추가 전에 기존 초과 데이터를 잘라 이후 unrelated UPDATE도 실패하지 않게 한다.
update trades
set
  buy_reason = left(buy_reason, 5000),
  sell_reason = left(sell_reason, 5000),
  reflection_note = left(reflection_note, 5000),
  improvement_note = left(improvement_note, 5000)
where
  char_length(buy_reason) > 5000
  or char_length(sell_reason) > 5000
  or char_length(reflection_note) > 5000
  or char_length(improvement_note) > 5000;

alter table trades
  add constraint trades_buy_reason_len_check
    check (buy_reason is null or char_length(buy_reason) <= 5000),
  add constraint trades_sell_reason_len_check
    check (sell_reason is null or char_length(sell_reason) <= 5000),
  add constraint trades_reflection_note_len_check
    check (reflection_note is null or char_length(reflection_note) <= 5000),
  add constraint trades_improvement_note_len_check
    check (improvement_note is null or char_length(improvement_note) <= 5000);
