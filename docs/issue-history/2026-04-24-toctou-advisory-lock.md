> 완료: 2026-04-24

# Spec: TOCTOU race → pg_advisory_xact_lock 원자화

## 배경 / 문제

FastAPI trades 라우터의 SELL/BUY/DELETE/PATCH 경로는 `acquire_for_user` 트랜잭션 내에서 `list_trades → validate → write → recalc_group_pnl` 순으로 동작한다. Postgres 기본 격리 수준(READ COMMITTED)에서는 predicate lock이 없어, 동시에 도착한 두 SELL 요청이 같은 보유량 스냅샷을 읽고 둘 다 validate를 통과해 보유량 음수(over-sell)가 발생할 수 있다. holdings 별도 테이블이 없어 `SELECT FOR UPDATE`를 쓸 수 없으므로 `pg_advisory_xact_lock` 을 사용한다.

## 목표

- `create_trade` / `update_trade`(PnL 영향 필드) / `delete_trade_endpoint` 세 mutation 경로 모두에서, 같은 `(user, account, ticker, country)` 그룹의 동시 요청이 직렬화된다.
- `pg_advisory_xact_lock(hashtextextended($1, 0))` 이 `list_trades` 이전에 호출되며, 트랜잭션 종료 시 자동 해제된다.
- 기존 150개 테스트가 모두 통과한다.
- lock이 list_trades 이전에 실행됨을 검증하는 신규 테스트가 통과한다.

## 설계

### 접근 방식

transaction-scoped advisory lock 도입. 키 `"{user_id}:{account_id}:{ticker_symbol}:{country_code}"` 를 `hashtextextended($1, 0)` 로 bigint 변환해 단일 인자 `pg_advisory_xact_lock(bigint)` 를 호출한다. `pg_advisory_lock`(session-level) 사용 금지 — Supavisor transaction mode pooler에서 leak.

`delete_trade_endpoint` 는 기존 `list_trades` 선행 구조로는 lock 전에 target group key를 알 수 없으므로, `fetchrow(trade_id, user_id)` 로 target을 먼저 조회하도록 재구조화.

### 주요 변경 파일

- `api/src/invest_note_api/db_ops/trades_repo.py` — `acquire_trade_group_lock` 함수 추가
- `api/src/invest_note_api/routers/trades.py` — 세 mutation 엔드포인트에 lock 획득 삽입; `delete_trade_endpoint` fetchrow-first 재구조화
- `api/tests/fake_pool.py` — `_is_internal`에 `PG_ADVISORY_XACT_LOCK` no-op 패턴 추가
- `api/tests/test_trades.py` — delete 테스트 응답 시퀀스 보정 + lock 순서 검증 신규 테스트

## 구현 체크리스트

- [x] `api/src/invest_note_api/db_ops/trades_repo.py` — `acquire_trade_group_lock` 추가
- [x] `api/src/invest_note_api/routers/trades.py` — import 추가 + `create_trade` lock 삽입
- [x] `api/src/invest_note_api/routers/trades.py` — `update_trade` PnL 분기 lock 삽입
- [x] `api/src/invest_note_api/routers/trades.py` — `delete_trade_endpoint` 재구조화
- [x] `api/tests/fake_pool.py` — `_is_internal` 확장
- [x] `api/tests/test_trades.py` — delete 테스트 보정 + 신규 lock 순서 테스트
- [x] `poetry run pytest api/tests/ -v` — 150개 전부 통과

## 우려사항 / 리스크

- 해시 충돌 (64-bit, 무시 가능 — 불필요 직렬화만 발생, 정합성 영향 없음)
- lock_timeout 미설정 (후속 작업: `SET LOCAL lock_timeout = '2s'`)
- 실제 Postgres race 재현 통합 테스트 미포함 (백로그: testcontainers 기반)
