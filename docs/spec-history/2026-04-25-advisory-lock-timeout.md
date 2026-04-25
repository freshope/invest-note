> 완료: 2026-04-25

# Spec: advisory lock timeout

## 배경 / 문제

`feature/toctou-advisory-lock`에서 `pg_advisory_xact_lock` 기반 그룹 직렬화를 도입했지만, lock 획득 대기 시간에 상한이 없습니다. 운영에서 같은 (user, account, ticker, country) 그룹에 동시 mutation이 몰리고 한쪽 트랜잭션이 늦어지면 뒤에 도착한 요청이 무한정 대기하면서 워커가 점유됩니다. `spec-history/2026-04-24-toctou-advisory-lock.md` 우려사항 섹션에 후속 작업으로 명시된 항목의 이행입니다.

## 목표

- `acquire_trade_group_lock` 호출이 2초 내 lock 획득에 실패하면 `asyncpg.exceptions.LockNotAvailableError` (sqlstate `55P03`)가 발생한다.
- 해당 에러는 클라이언트에 `409 Conflict` + 한국어 안내 메시지로 변환되어 응답된다.
- 기존 lock-순서 단위 테스트가 그대로 통과하며, `SET LOCAL lock_timeout`이 advisory lock보다 먼저 실행됨이 새로 검증된다.
- lock_timeout 발생 시 409를 반환함을 검증하는 테스트가 추가된다.

## 설계

### 접근 방식

- `acquire_trade_group_lock` 내부에 `SET LOCAL lock_timeout = '2s'` 실행을 advisory lock 직전에 추가. 호출자 모두 `acquire_for_user` → `conn.transaction()` 안에 있으므로 `SET LOCAL` 안전.
- 에러 변환은 `main.py`에 전역 exception handler 한 곳에서 수행 (`LockNotAvailableError` → 409). `db_ops`가 `errors.APIError`를 import하지 않아 의존 방향이 깔끔.

### 주요 변경 파일

- `api/src/invest_note_api/db_ops/trades_repo.py` — `acquire_trade_group_lock`에 `SET LOCAL lock_timeout = '2s'` 추가.
- `api/src/invest_note_api/main.py` — `LockNotAvailableError` 전역 exception handler 등록 (409).
- `api/tests/test_trades.py` — SET LOCAL 순서 검증 헬퍼 + lock_timeout → 409 테스트 추가.

## 구현 체크리스트

- [x] `acquire_trade_group_lock`: `SET LOCAL lock_timeout = '2s'` 실행 추가.
- [x] `main.py`: `LockNotAvailableError` → 409 전역 handler 등록.
- [x] `test_trades.py`: `_assert_lock_timeout_before_lock` 헬퍼 + 409 변환 테스트 추가.
- [x] `pytest tests/test_trades.py -q` 통과.
- [x] `pyright src` 통과.

## 우려사항 / 리스크

- 같은 트랜잭션 안의 후속 row-lock(INSERT/UPDATE)에도 2s 상한이 적용됨. 일반 운영에서는 빠르므로 영향 없음.
- 클라이언트 재시도 정책은 이번 spec 범위 밖.
