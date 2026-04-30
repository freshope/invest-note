# Spec: trades 검색 필터 strict 정리 (`ticker_symbol` invariant)

## 배경 / 문제

`api/src/invest_note_api/routers/trades.py:102-107` 의 `GET /api/trades?ticker=...` 핸들러는
`t.ticker_symbol == ticker or t.asset_name == ticker` 로 OR 매칭한다.

2026-04-30 `docs/decisions.md` 결정에서 `Trade.ticker_symbol` 은 항상 채워진다는 invariant 를 명시하고,
같은 OR 분기를 갖던 `domain/holdings.py::_is_flexible_match` 와 `routers/portfolio.py` 의 `/holding` SQL
은 이미 strict 정책으로 통일되었다. `routers/trades.py` 의 OR 분기만 잔존해 정책 부정합 상태이다.

추가 사실:
- 호출처 두 곳(`app/src/app/(app)/records/page.tsx:26`, `app/src/components/home/HoldingsList.tsx:28`)
  중 ticker 파라미터를 사용하는 쪽은 `HoldingsList` 한 곳뿐이고, 거기서 보내는 `pos.ticker` 값은
  `app/src/lib/portfolio.ts:63` 에서 `trade.ticker_symbol ?? trade.asset_name` 으로 채워진다.
  invariant 가 유지되는 한 항상 `ticker_symbol` 과 동일하다.
- 기존 테스트 `api/tests/test_trades.py::TestListTrades::test_list_ticker_filter` 는 ticker_symbol
  매칭만 검증하고, asset_name 분기에 대한 테스트는 없다 — 의도적 기능이라 보기 어려움.

따라서 OR 분기는 dead branch 로 판단해 strict 로 정리한다.

## 목표

- `GET /api/trades?ticker=<X>&country=<Y>` 가 `ticker_symbol == X` 인 거래만 반환한다 (asset_name 매칭 제거).
- `decisions.md` 2026-04-30 항목과 코드의 매칭 정책이 정확히 일치한다.
- 회귀 방지를 위한 단위 테스트가 추가되어 strict 동작을 보장한다.

## 설계

### 접근 방식

1. `routers/trades.py:106` 의 `(t.ticker_symbol == ticker or t.asset_name == ticker)` 를
   `t.ticker_symbol == ticker` 로 단축. invariant 는 이미 다른 코드 경로에서 신뢰하고 있으므로 별도 주석은
   불필요(2026-04-30 결정이 single source of truth).
2. `api/tests/test_trades.py::TestListTrades` 에 strict 회귀 테스트 추가 — `asset_name` 만 일치하는
   거래는 결과에 포함되지 않음을 확인.
3. `docs/backlog.md` 의 해당 체크박스를 완료 처리하고 정리 사실을 한 줄 메모로 남긴다.
4. `docs/decisions.md` 2026-04-30 항목 본문에 `routers/trades.py` 도 strict 로 통일됐다는 한 줄을
   추가하여 정책 일관성 기록을 갱신한다.

### 주요 변경 파일

- `api/src/invest_note_api/routers/trades.py` — 106줄 OR 분기 제거.
- `api/tests/test_trades.py` — strict 매칭 회귀 테스트 1건 추가 (`asset_name` 만 일치하는 거래 제외 확인).
- `docs/backlog.md` — 19줄 항목 체크/완료 처리.
- `docs/decisions.md` — 2026-04-30 항목에 `routers/trades.py` 정리 사실 한 줄 추가.

### 재사용 대상

- 기존 테스트 헬퍼 `_make_trade_row`, `_to_record`, `FakeConnection`, `_patch_trades`
  (`api/tests/test_trades.py`) — 신규 테스트도 동일 헬퍼 사용.

## 구현 체크리스트

- [ ] `routers/trades.py:106` OR 분기를 strict 비교로 변경.
- [ ] `tests/test_trades.py` 에 strict 회귀 테스트 추가 (asset_name 만 일치하는 row 제외).
- [ ] 백엔드 테스트 실행 (`cd api && poetry run pytest tests/test_trades.py -q`).
- [ ] `docs/backlog.md` 해당 항목 체크/제거.
- [ ] `docs/decisions.md` 2026-04-30 항목에 trades.py 정리 한 줄 추가.

## 우려사항 / 리스크

- invariant 가 깨진 레거시 row(`ticker_symbol = ''` 또는 NULL) 가 실제로 존재한다면, 해당 종목 카드
  탭 시 거래 목록이 비어 보일 수 있다. 이는 2026-04-30 decisions.md 트레이드오프에 이미 동일하게
  기록된 위험이며 portfolio.py 정리 후 회귀 보고가 없으므로 동일 정책으로 진행한다.
  (검증 쿼리는 decisions.md 에 명시됨: `SELECT count(*) FROM trades WHERE ticker_symbol = '' OR ticker_symbol IS NULL`)
- 프론트엔드 `portfolio.ts:63` 의 `?? trade.asset_name` fallback 은 이번 작업 범위 밖. 별도 백로그
  항목으로 분리할 가치가 있는지는 후속 결정.
