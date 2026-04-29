# Spec: 백엔드 simplify 퀵윈 묶음

## 배경 / 문제

2026-04-29 backend 전체 simplify 리뷰에서 식별된 14개 항목 중, **변경 범위가 작고 리스크가 낮은** 7개 항목을 한 PR로 묶어 정리한다. 큰 리팩터링(typed body 전환, response_model 도입, FIFO walker 통합 등)은 별도 PR로 미룬다. 작업의 의도는 hot path 1건(`get_holding`)의 풀 테이블 fetch를 좁힘과 동시에, 라우터/도메인 전반에 흩어져 있던 자잘한 중복·인라인 fallback·dead 코드를 한꺼번에 정리해 다음 큰 작업에 깨끗한 출발점을 만드는 것.

## 목표

- `routers/portfolio.py:get_holding`이 사용자 전체 거래가 아닌 (account, ticker/asset, country) 조건으로 좁혀진 행만 조회한다.
- `routers/trades.py`에서 trade fetch-by-id 3곳, account 존재 검증 2곳이 `db_ops` 헬퍼 호출로 단일화된다.
- `domain/trade_types`에 `trade_identifier(t)` / `trade_country(t)` 헬퍼가 추가되고, 사용처 18곳이 헬퍼 호출로 교체된다.
- `domain/trade_utils`에 `kst_date_to_utc(date_or_datetime)` 헬퍼가 추가되고 import commit 경로 + `_traded_at_transform`이 공통 헬퍼를 사용한다.
- `routers/trades.py`의 미사용 import 3개·로컬 변수 2개·broad-except 메시지의 raw exception 노출이 제거된다.
- 기존 223개 백엔드 테스트가 모두 통과한다.

## 설계

### 접근 방식

신규 헬퍼는 모두 기존 모듈에 추가하고 (새 파일 없음) 사용처를 일괄 교체한다. 동작 변경이 있는 항목은 #3(`get_holding` 쿼리 좁히기) 하나뿐이며, 나머지는 순수 리팩터링이라 단위 테스트로 회귀 검증한다.

#3은 입력 파라미터 4개(`account_id`/`ticker`/`asset_name`/`country`)를 그대로 활용해 SQL `WHERE` 조건으로 옮긴다. `compute_total_holding` / `compute_wac`이 동일 4개 인자로 in-memory 필터하므로, DB로 푸시하면 결과 동일성이 자명하다.

#7 `kst_date_to_utc`는 `domain/trade_utils.py`에 추가한다 (이미 `to_kst`가 있는 모듈). 시그니처: `kst_date_to_utc(d: date, t: time = time(9, 0)) -> datetime`. import commit의 `datetime.combine(...)+astimezone(...)`을 한 호출로 교체.

### 주요 변경 파일

- `api/src/invest_note_api/routers/trades.py` — 미사용 import/변수 정리, broad-except 메시지 sanitize, fetch-by-id/account-exists 헬퍼 호출, country fallback 헬퍼 사용, KST→UTC 헬퍼 사용
- `api/src/invest_note_api/routers/portfolio.py` — `get_holding`을 좁힌 쿼리로 교체
- `api/src/invest_note_api/db_ops/trades_repo.py` — `get_trade(conn, trade_id, user_id)`, `assert_account_exists(conn, account_id)` 헬퍼 추가
- `api/src/invest_note_api/domain/trade_types.py` — `trade_identifier(t)`, `trade_country(t)` 헬퍼 추가
- `api/src/invest_note_api/domain/trade_utils.py` — `kst_date_to_utc(d, t=time(9,0))` 헬퍼 추가
- `api/src/invest_note_api/domain/portfolio.py`, `domain/holdings.py`, `domain/realized_pnl.py`, `domain/analysis/concentration.py` — 인라인 fallback을 헬퍼 호출로 교체
- `api/src/invest_note_api/schemas/trade.py` — `_traded_at_transform`이 가능한 경우 `kst_date_to_utc` 또는 공통 파서 사용 (기존 ISO suffix 휴리스틱은 유지)

## 구현 체크리스트

- [ ] **#1 미사용 import/변수 정리** — `routers/trades.py:45-47` `RESULT_BREAKEVEN/FAIL/SUCCESS` import 제거, `:375` `future_errors`, `:539` `now_utc` 미사용 변수 제거. `poetry run ruff check` 의 F401/F841 신규 에러 0건 확인.
- [ ] **#2 broad-except 메시지 sanitize** — `routers/trades.py:606` `except Exception as e:` 의 사용자 노출 메시지에서 `{e}` 제거. `logger.warning(..., exc_info=True)` 추가하고 사용자에게는 일반화된 문구만.
- [ ] **#7-a `kst_date_to_utc` 헬퍼 추가** — `domain/trade_utils.py`에 `kst_date_to_utc(d: date, t: time = time(9, 0)) -> datetime` 추가. unit test 1개 (`tests/test_trade_utils.py` 또는 동등 위치).
- [ ] **#7-b 사용처 교체** — `routers/trades.py:564-565` import commit 경로의 `datetime.combine + astimezone` 호출을 헬퍼로 교체. `schemas/trade.py:_traded_at_transform`은 입력이 `date` 또는 ISO string 둘 다이므로 헬퍼 적용 가능 범위만 교체 (휴리스틱은 유지).
- [ ] **#6-a `trade_identifier` / `trade_country` 헬퍼 추가** — `domain/trade_types.py`에 두 함수 추가. 시그니처: `trade_identifier(t: Trade) -> str`, `trade_country(t: Trade) -> str`.
- [ ] **#6-b 사용처 교체** — `domain/portfolio.py`(80,81,216,217), `domain/holdings.py`(44,47,60,151,152), `domain/realized_pnl.py`(39,47,49), `domain/analysis/concentration.py:55`, `routers/trades.py`(116,157,175,199) 의 인라인 fallback을 헬퍼 호출로 일괄 교체. `lot_key` f-string도 `f"{trade_identifier(t)}:{trade_country(t)}"`로.
- [ ] **#4 `get_trade` 헬퍼 추가 + 사용처 교체** — `db_ops/trades_repo.py`에 `async def get_trade(conn, trade_id: str, user_id: str) -> Trade | None`. `routers/trades.py:218,283,322`의 fetch + `Trade(**dict(row))` + 404 raise 패턴을 헬퍼 호출로 교체.
- [ ] **#5 `assert_account_exists` 헬퍼 추가 + 사용처 교체** — `db_ops/trades_repo.py`에 `async def assert_account_exists(conn, account_id: str) -> None` (없으면 `APIError("올바른 계좌를 선택해주세요.", 400)` raise). `routers/trades.py:139,512` 두 곳 교체.
- [ ] **#3 `get_holding` 쿼리 좁히기** — `routers/portfolio.py:48-67`의 풀 테이블 SELECT을 `WHERE user_id=$1 AND account_id=$2 AND (ticker_symbol=$3 OR asset_name=$4) AND country_code=$5 ORDER BY traded_at ASC`로 교체. `compute_total_holding`/`compute_wac` 호출 인자는 그대로 유지 (이미 작은 결과셋이므로 in-memory 필터는 빠른 no-op).
- [ ] **회귀 검증** — `cd api && poetry run pytest -q` 223 pass. `poetry run ruff check src/invest_note_api/routers/trades.py` 가 사전 존재 5개 에러에서 0개로 줄어드는지 확인.

## 우려사항 / 리스크

- **#3 동작 차이** — `compute_total_holding`이 `ticker`가 None일 때 `asset_name`으로만 매칭하는 분기가 있다. 새 SQL의 `(ticker_symbol = $3 OR asset_name = $4)` 조건이 이 의미와 일치하는지 `domain/holdings.py:35-`(`_is_flexible_match`)와 대조 후 확정. 불일치 시 SQL을 `((ticker_symbol IS NOT NULL AND ticker_symbol = $3) OR asset_name = $4)` 로 보정.
- **#6 의도하지 않은 의미 변경** — `lot_key` 빌더(`domain/holdings.py:60`, `domain/portfolio.py:217`)가 raw `trade.country_code`(빈 문자열 가능)를 사용하고 있을 수 있는데, fallback 헬퍼로 바꾸면 `""` → `KR` 정규화가 일어난다. DB 데이터에 빈 문자열이 있는지 확인 — 있으면 키가 달라져 그룹핑 결과가 변할 수 있음. (현재 라우터/도메인 다른 사이트들은 이미 fallback을 적용 중이라 정합성은 오히려 개선되는 방향.)
- **#7 `_traded_at_transform`** — KST 휴리스틱이 복잡해 헬퍼 적용 범위가 제한적일 수 있다. 적용이 어렵다면 `_traded_at_transform`은 그대로 두고 import commit 경로만 교체.
