# Spec: recalc_group_pnl 변경 row만 UPDATE 최적화

## 배경 / 문제

`PNL_AFFECTING_FIELDS`에 `reasoning_tags`/`emotion`이 포함된 이후, BUY 메타만 단독으로 변경해도
`acquire_trade_group_lock` + `recalc_group_pnl`이 트리거되어 그룹 내 **모든 SELL row**가 매번
`executemany`로 UPDATE된다. 실제로는 BUY 메타 변경의 영향은 latest 소비된 BUY를 참조하는
일부 SELL row의 `reasoning_tags`/`emotion`/`strategy_type`에만 반영되므로, 나머지 SELL row는
이전 값과 동일하지만 똑같이 UPDATE 발행되어 DB write 부하가 누적된다.

## 목표

- `recalc_group_pnl`이 `compute_group_pnl()` 결과와 **기존 SELL row의 7개 PnL 필드**를 비교해
  실제로 값이 달라진 row에만 UPDATE를 발행한다.
- 변경된 row가 0개이면 `executemany` 호출 자체를 스킵한다 (no-op).
- 기존 mutation 경로 (POST/PATCH/DELETE/import commit) 의 동작·정합성은 그대로 유지된다.

## 설계

### 접근 방식

`api/src/invest_note_api/db_ops/pnl_sync.py:recalc_group_pnl` 내부에서:

1. `pnl_map = compute_group_pnl(trades, key)` 결과는 그대로 유지.
2. 입력 `trades` 리스트에서 `pnl_map.keys()` (= sell_id) 에 해당하는 SELL `Trade`를 id 인덱스로 매핑.
   호출 측은 항상 DB에서 막 읽었거나 mutation 직후의 fresh trades를 넘기므로, SELL row의
   `profit_loss`/`avg_buy_price`/`holding_days`/`strategy_type`/`reasoning_tags`/`emotion`/`result`는
   "직전 recalc 결과 또는 NULL" 상태이다.
3. 각 entry에 대해 위 7개 필드를 기존 SELL Trade와 비교:
   - 숫자(`profit_loss`, `avg_buy_price`): `math.isclose(rel_tol=1e-9, abs_tol=1e-9)` — DB round-trip
     후의 미세 부동소수 오차로 false-positive를 막기 위함. `holding_days`는 int이므로 `==` 비교.
   - `strategy_type`/`emotion`/`result`: `==` 비교 (None 포함).
   - `reasoning_tags`: list 동등성(`==`) 비교. `compute_group_pnl`은 결정적이므로 동일 입력에
     동일 순서를 보장한다.
4. 변경된 row만 `rows`에 추가. `rows`가 비면 즉시 return (UPDATE 스킵).
5. SQL 문자열·파라미터 순서·`executemany` 호출은 그대로 유지하여 회귀 위험 최소화.

### 주요 변경 파일

- `api/src/invest_note_api/db_ops/pnl_sync.py` — `recalc_group_pnl`에 변경 row 필터링 + early return.
- `api/tests/test_pnl_sync.py` (신규) — 단위 테스트:
  - 변경 없으면 `executemany` 미호출
  - 일부 SELL만 변경되면 해당 row만 파라미터에 포함
  - 신규 SELL (기존 PnL 필드 NULL) 은 항상 UPDATE 대상

## 구현 체크리스트

- [x] `recalc_group_pnl`에 기존 SELL row 인덱스 + 7개 필드 비교 + early return 추가
- [x] `api/tests/test_pnl_sync.py` 신규 작성 (FakeConn으로 `executemany` 호출 캡처)
- [x] 백엔드 테스트 통과 (`cd api && poetry run pytest -q`) — 256 passed

## 우려사항 / 리스크

- **부동소수 비교**: `compute_group_pnl`은 입력에 따라 결정적이지만, 기존 DB 값은 numeric/double
  round-trip을 거치므로 미세 오차 가능. `math.isclose(rel_tol=1e-9, abs_tol=1e-9)`로 흡수.
- **reasoning_tags 순서**: walker가 latest BUY의 tags를 그대로 전달하므로 동일 입력 → 동일 순서.
  순서가 흔들릴 가능성은 없음 (`_meta_from_consumed_latest`).
- **호출 경로 의존**: 호출 측이 fresh trades를 넘긴다는 가정이 있음 — 현재 4개 호출 경로
  (`create_trade`, `update_trade`, `delete_trade_endpoint`, `import_commit`) 모두 만족하지만,
  새 호출자 추가 시 동일 가정 유지가 필요.
