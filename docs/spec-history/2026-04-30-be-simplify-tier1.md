# Spec: BE simplify Tier 1 (정확성·핫패스·캐시·재사용)

## 배경 / 문제

`/simplify be 전체 조사` 결과 발견된 Tier 1 항목 중 도메인 시그니처 변경을 동반하지 않는 4건을 정리한다. 자주 호출되는 mutation/summary/시세 fetch 경로의 효율과 정확성을 개선한다.

- `accounts` 카운트 GROUP BY에 `user_id` 필터가 없어 RLS off 시 풀스캔, 인덱스 미활용
- `portfolio.py` summary 라우터가 `db_ops/trades_repo.py`의 `list_trades_with_account`와 동일한 SQL을 인라인 복제
- 거래 mutation(POST/PATCH/DELETE) 및 `import_commit`이 매번 사용자 전체 거래를 풀 페치한 뒤 그룹으로 필터 — 거래가 누적되면 mutation당 비용이 선형 증가
- 시세 캐시 미스 시 동일 종목에 대해 동시 요청 N건이 모두 `_fetch_kr_price`를 호출하는 thundering herd

## 목표

- `GET /api/accounts` 의 trade 카운트 쿼리가 user 스코프로 동작하고, EXPLAIN 시 `trades_user_id_idx` 또는 동등 인덱스를 사용한다.
- `GET /api/portfolio/summary` 의 trades+accounts 페치는 `db_ops/trades_repo.py:list_trades_with_account` 단일 함수 사용.
- `POST/PATCH/DELETE /api/trades`, `POST /api/trades/import/commit` 의 mutation 경로에서 `list_trades(user_id)` 풀 페치가 사라지고, 대상 그룹 거래만 페치한다.
- `external/quotes.py` 의 동일 키 N개 동시 요청은 `_fetch_kr_price` 를 1회만 호출한다.
- 모든 변경 후 외부 동작(응답 schema·값)은 동일하다. `cd api && poetry run pytest -q` 통과.

## 설계

### 접근 방식

- 4개의 작은 변경을 Step별 독립 commit으로 나눈다(Step 1~4).
- 모든 변경은 외부 API 응답 동작을 유지하며, 신규 헬퍼/리포 함수는 기존 도메인 의미와 일치한다.
- Step 5(portfolio summary 풀스캔 통합)는 `domain/portfolio.py` 시그니처 변경을 동반하므로 본 spec에서 제외, `docs/backlog.md`에 후속 항목으로 등록.

### 주요 변경 파일

- `api/src/invest_note_api/routers/accounts.py` — Step 1: GROUP BY 쿼리에 `WHERE user_id = $1` 추가
- `api/src/invest_note_api/routers/portfolio.py` — Step 2: 인라인 SQL → `list_trades_with_account` 호출
- `api/src/invest_note_api/db_ops/trades_repo.py` — Step 3: `list_trades_in_group(conn, user_id, key)` 신규 함수
- `api/src/invest_note_api/routers/trades.py` — Step 3: POST/PATCH/DELETE/import_commit 4곳 호출 교체
- `api/src/invest_note_api/external/quotes.py` — Step 4: `_inflight: dict[str, asyncio.Future]` 추가, `_get_cached` owner/follower 분기

### 재사용 함수

- `db_ops/trades_repo.py:57 list_trades_with_account`
- `domain/realized_pnl.py:50 is_same_group`, `domain/realized_pnl.py:41 trade_to_group_key`
- `domain/realized_pnl.py:TradeGroupKey` (Step 3 신규 함수의 인자)

## 구현 체크리스트

- [x] Step 1 — `routers/accounts.py` SQL에 `WHERE user_id = $1` 추가
- [x] Step 1 — `pytest tests/test_accounts.py -q` 통과 + commit (86865a2)
- [x] Step 2 — `routers/portfolio.py` 인라인 SQL 제거, `list_trades_with_account` 호출
- [x] Step 2 — `pytest tests/test_portfolio.py -q` 통과 + commit (19a3347)
- [x] Step 3 — `db_ops/trades_repo.py` `list_trades_in_group(conn, user_id, key)` 신규 함수
- [x] Step 3 — `routers/trades.py` POST/PATCH/DELETE 호출 교체
- [x] Step 3 — `routers/trades.py` `import_commit` 그룹 partition 선분할 + 그룹별 fetch + recalc
- [x] Step 3 — 회귀 테스트 `test_commit_fetches_per_group` 으로 갱신 + commit (a8d4178)
- [x] Step 4 — `external/quotes.py` `_inflight` 맵 추가, `_get_cached` 재작성
- [x] Step 4 — `tests/test_quotes.py` 신규 — single-flight 동시 호출 fetch 1회 검증
- [x] Step 4 — `pytest -q` 259개 통과 + commit (5932ce7)
- [x] spec-current → issue-history 이동, backlog 후속 항목 추가

## 우려사항 / 리스크

- **Step 3 `import_commit` 그룹 분할**: 기존 동작은 user 전체 `existing_sigs` 셋으로 dedup. 그룹별로 분할하면 dedup 범위가 그룹 내로 좁아진다. 단, 시그니처 키에 `account_id+ticker+date+type+qty+price` 가 모두 포함되므로 다른 그룹의 sig가 매칭될 일이 없어 동작 동일. (검증 필요)
- **Step 4 single-flight**: 첫 fetch 실패 시 follower들도 같은 예외를 받게 됨 — 기존 동작과 동일(`asyncio.gather(return_exceptions=True)` 가 위에서 흡수).
- **Step 1 RLS 의존**: 현재 RLS가 user_id를 강제하고 있어도 결과는 안전하지만 풀스캔 비용이 발생. 명시 필터로 인덱스 활용 보장.
