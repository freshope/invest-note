# Spec: BE simplify — `/api/trades` ticker 필터 SQL push

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md` 의 "FE simplify"·"BE simplify" 잔여 항목 2개는 사실상 한 가지 — `/api/trades` 페이지네이션 + ticker 필터 SQL push — 이며 cleanup-trio (`docs/spec-history/2026-05-03-simplify-cleanup-trio.md`) 에서 "BE+FE 동반 큰 작업" 이라는 이유로 명시적으로 미뤄졌다.

이 중 ticker 필터 SQL push 만은 **records 화면 변경 없이 BE 단독으로** 처리 가능하고 독립적 가치가 있다:

- 현재 `list_trades_endpoint` (`api/src/invest_note_api/routers/trades.py:114-137`) 는 `list_trades_with_account` 로 user 의 **모든** trades 를 fetch 한 뒤 Python 메모리에서 `ticker` / `country` 로 필터링한다.
- HoldingsList (`app/src/components/home/HoldingsList.tsx:29-32`) 는 카드 클릭 시 `tradesApi.list({ ticker, country })` 로 호출하는데, BE 가 사용자의 전체 거래를 매번 가져오므로 종목당 트래픽이 user 거래 수에 비례한다.
- `list_trades_with_account` 의 SQL (`api/src/invest_note_api/db_ops/trades_repo.py:97-110`) 에 조건부 WHERE 만 추가하면 Python 후처리가 사라진다.

페이지네이션은 별도 검증 후(거래 수 분포·records 첫 페인트 시간) 결정하기로 했으므로 본 spec 범위 외이다.

## 목표

- HoldingsList 가 호출하는 `/api/trades?ticker=&country=` 가 SQL WHERE 절에서 곧바로 필터된 행만 반환한다 (사용자 전체 trades 를 가져와서 Python 에서 후처리하지 않음).
- 라우터의 Python 후처리 (`routers/trades.py:130-135`) 가 제거되고, 응답 바디·400 검증·기존 호출처 동작은 그대로 유지된다.
- `cd api && poetry run pytest -q` 통과.

## 설계

### 접근 방식

`list_trades_with_account` 시그니처에 `ticker: str | None = None, country: str | None = None` 옵션 인자를 추가하고, SQL 에 조건부 WHERE 를 push 한다. 파라미터가 None 이면 기존 동작(전량 반환). `country` 정규화는 `domain/trade_types.py:57-59` 의 `trade_country(t) = trade.country_code or DEFAULT_COUNTRY` 의 SQL 등가식인 `COALESCE(NULLIF(t.country_code, ''), 'KR') = $N` 을 사용한다 — 같은 파일 `list_trades_for_group` (`trades_repo.py:86`) 가 이미 동일 패턴으로 동작 중이다.

라우터는 ticker 검증/`[:30]` 정규화 후 그대로 repo 에 위임하고, ticker 가 있을 때만 country 도 함께 push (현재 Python 분기와 동일한 의미).

### 주요 변경 파일

- `api/src/invest_note_api/db_ops/trades_repo.py:97-110` — `list_trades_with_account(conn, user_id, *, ticker=None, country=None)` 로 시그니처 확장. SQL WHERE 에 `($2::text IS NULL OR t.ticker_symbol = $2)` 와 `($3::text IS NULL OR COALESCE(NULLIF(t.country_code, ''), 'KR') = $3)` 추가. asyncpg 호출에 `ticker`, `country` 인자 전달.
- `api/src/invest_note_api/routers/trades.py:114-137` — ticker 검증/`[:30]` 유지. `list_trades_with_account(conn, user.id, ticker=ticker, country=country if ticker else None)` 호출로 변경. 130-135 줄의 Python 후처리 블록 제거. `trade_country` import 가 더 이상 쓰이지 않으면 삭제.
- `api/tests/test_trades.py:164-186` — `FakeConnection` 은 WHERE 를 모사하지 않으므로:
  - `test_list_ticker_filter` (라인 164): 200 + 응답 shape 검증으로 유지 (그대로 통과).
  - `test_list_ticker_filter_strict_ticker_symbol_only` (라인 174-186): SQL push 후 Python 에서 dead-branch 검증이 무의미. **삭제하거나** repo 단위 테스트로 변환 (FakeConnection 의 fetch 호출 인자를 캡처해서 `$2 = "005930"` 가 전달됐는지만 확인). 단순함 우선으로 삭제 권장 — `decisions.md` 에 한 줄 메모.
- `docs/backlog.md` — "BE simplify > 효율 / 핫패스" 의 `GET /api/trades` 항목에 "ticker SQL push 부분만 처리됨, 페이지네이션은 별도 검증 후 결정" 메모 추가.

### 페이지네이션은 본 spec 범위 외

- records 화면(`app/src/app/(app)/records/page.tsx`)·`TradeList`·상세 패널 `allTrades` 사용 흐름은 건드리지 않는다.
- `tradesApi.list()` (FE) 시그니처/queryKey 도 변경 없음.
- 페이지네이션 필요성 검증(거래 수 분포·체감 성능)은 본 spec 종료 후 별도로 진행하고, 결과에 따라 backlog 업데이트.

## 구현 체크리스트

- [x] `list_trades_with_account` 에 `ticker`/`country` keyword-only 인자 추가 + SQL WHERE 조건부 push
- [x] `list_trades_endpoint` 의 Python 후처리 제거 + repo 호출에 인자 전달, 미사용 import (`trade_country`) 정리
- [x] `test_list_ticker_filter_strict_ticker_symbol_only` 를 `test_list_ticker_pushed_to_sql` 로 대체 — fetch 인자(ticker=$2, country=$3) 캡처해 SQL push 자체를 검증 (삭제 대신 업그레이드 → decisions.md 메모 불필요)
- [x] `cd api && poetry run pytest -q` 통과 (251 passed)
- [x] `docs/backlog.md` 의 BE/FE simplify 양쪽 항목에 처리 메모 추가
- [x] (선택) 페이지네이션 필요성 검증 — backlog 메모로 이관 (거래 수 분포 측정은 별개 작업으로 진행)

## 검증

1. **단위 테스트**: `cd api && poetry run pytest tests/test_trades.py -q` — `test_list_ticker_filter` / `test_list_invalid_ticker_400` 통과, ticker 미지정 호출 (`test_list`) 동작 변화 없음.
2. **전체 테스트**: `cd api && poetry run pytest -q` 통과.
3. **수동 검증 (가능 시)**:
   - 홈 대시보드의 보유 종목 카드 클릭 → 상세 패널이 해당 종목 거래만 정상 노출.
   - records 페이지 진입 → 전체 거래 목록·groupByDate·account filter 가 변화 없이 동작.

## 우려사항 / 리스크

- `list_trades_with_account` 호출처 추가 사용은 없음 — 라우터 한 곳에서만 호출 (grep 확인 필요, 변경 시 함께 처리).
- `FakeConnection` 이 SQL WHERE 를 모사하지 않으므로 SQL push 자체의 정합성은 단위 테스트로 직접 보증할 수 없다. 같은 SQL 패턴이 `list_trades_for_group` 에서 production 동작 중이라는 점이 1차 신뢰 근거.
- 페이지네이션은 본 spec 범위 외 — 진행 시 records 화면/상세 패널/accounts 응답 분리까지 별도 spec 으로 다룸.
