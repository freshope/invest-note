# Spec: insert_trade ↔ insert_trades_bulk SQL 중복 제거

> 완료: 2026-04-30

## 배경 / 문제

`db_ops/trades_repo.py`의 `insert_trade`(L111-149)와 `insert_trades_bulk`(L231-278)가
같은 19개 컬럼·19개 placeholder·15줄 dict-to-tuple 매핑을 각각 따로 가지고 있다.
컬럼이 추가될 때 한 쪽만 갱신되면 임포트 경로와 단건 등록 경로의 동작이 silently drift할 수 있다.
백로그 (HIGH 구조 개선) 항목으로 등록되어 있고, 단일 source of truth가 필요하다.

## 목표

- 19-컬럼 INSERT 문/매핑이 trades_repo.py 안에서 **단 한 곳만** 유지된다.
- `insert_trade`는 단건 RETURNING 동작(반환값 `{id, trade_type}`)을 그대로 유지한다.
- `insert_trades_bulk`는 `executemany` 동작과 반환값(삽입 행 수)을 그대로 유지한다.
- 외부 호출자 시그니처(`routers/trades.py:186`, `:574`)와 기존 테스트(`tests/test_trades.py`)는 수정 없이 통과한다.
- `cd api && poetry run pytest tests/test_trades.py -q` 통과.

## 설계

### 접근 방식

`executemany`는 RETURNING과 호환되지 않으므로 백로그 표현 그대로 "bulk를 [data]로 호출"하는 방식은 부적합.
실질적인 중복 — 컬럼 목록·placeholder·data→tuple 매핑 — 만 모듈 상수/헬퍼로 추출하고,
두 함수는 SQL 실행 방식(`fetchrow` vs `executemany`)만 각자 유지한다.

추출 단위:
- `_TRADE_INSERT_SQL`: 모듈 private 상수. `INSERT INTO trades (...) VALUES (...)` 본문(컬럼 + placeholder).
- `_trade_insert_params(user_id, data) -> tuple`: dict → 19-튜플 매핑 헬퍼. 기본값(`MARKET_TYPE_STOCK`, `DEFAULT_COUNTRY`, `[]`, 0, "")까지 포함.

두 함수는 다음과 같이 단순화된다:

- `insert_trade`: `f"{_TRADE_INSERT_SQL} RETURNING id, trade_type"` + `fetchrow(*_trade_insert_params(...))` → `dict(row)` 반환.
- `insert_trades_bulk`: 빈 리스트 가드 유지, `params = [_trade_insert_params(user_id, d) for d in rows]`, `executemany(_TRADE_INSERT_SQL, params)`, `return len(rows)`.

다른 코드 경로(트리거, validate, recalc 등)는 영향이 없다.

### 주요 변경 파일

- `api/src/invest_note_api/db_ops/trades_repo.py` — `_TRADE_INSERT_SQL` 상수 + `_trade_insert_params` 헬퍼 추가, `insert_trade`/`insert_trades_bulk` 본문을 헬퍼 사용으로 교체.

## 구현 체크리스트

- [x] `trades_repo.py`에 `_TRADE_INSERT_SQL` 상수와 `_trade_insert_params` 헬퍼 추가
- [x] `insert_trade`를 헬퍼 기반으로 단순화 (`RETURNING id, trade_type` 유지)
- [x] `insert_trades_bulk`를 헬퍼 기반으로 단순화 (executemany + 행 수 반환 유지)
- [x] `cd api && poetry run pytest tests/test_trades.py -q` 통과 확인 (36 passed)
- [x] backlog.md에서 본 항목 제거

## 우려사항 / 리스크

- `_trade_insert_params`의 기본값/키 누락이 한 함수만 영향을 미치던 구조였다면 통합 후 양쪽 모두 영향을 받게 된다 — 다만 현재 두 함수의 매핑이 이미 동일하므로 의미 변화는 없음.
- FakeConnection 기반 테스트는 SQL 문자열을 기록만 할 뿐 정확 매칭하지 않아 영향 없음(스파이 코드 라인 92-115 확인).
- `executemany`는 RETURNING 미지원 → 백로그 표현(`[data]`로 호출 후 RETURNING 추가)을 글자 그대로 따르지 않고, 동일한 효과(공통 SQL/params)만 달성.
