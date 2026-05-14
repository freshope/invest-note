> 완료: 2026-04-30

# Spec: 임포트 commit 루프 N+1 제거

## Background / Problem

거래내역서 임포트 commit 경로가 그룹별 bulk insert 이후 `list_trades(conn, user.id)`를 다시 호출한다. 여러 종목을 한 번에 임포트하면 사용자 전체 거래 목록을 그룹 수만큼 반복 조회해 DB 부하와 응답 시간이 커진다.

## Goals

- `/api/trades/import/commit`에서 사용자 전체 거래 조회를 commit 시작 시 1회로 제한한다.
- bulk insert 후 삽입된 거래를 메모리의 거래 목록에 반영해 `recalc_group_pnl` 입력으로 사용한다.
- 그룹 단위 advisory lock, 중복 skip, PnL 재계산 동작은 유지한다.

## Design

### Approach

`insert_trades_bulk`가 삽입된 `Trade` 행을 `RETURNING *`으로 반환하도록 바꾸고, import commit 루프는 반환된 거래를 `all_trades`에 append한 뒤 해당 그룹 PnL을 재계산한다. 이렇게 하면 그룹마다 전체 거래를 다시 fetch하지 않아도 새 SELL id를 포함한 최신 계산 입력을 확보할 수 있다.

### Primary Files

- `api/src/invest_note_api/db_ops/trades_repo.py` - bulk insert가 삽입된 거래 행을 반환하도록 변경
- `api/src/invest_note_api/routers/trades.py` - import commit 루프에서 메모리 거래 목록 갱신 후 PnL 재계산
- `api/tests/test_trades.py` - import commit이 전체 거래 목록을 반복 조회하지 않는지 검증

## Implementation Checklist

- [x] `insert_trades_bulk` 반환값을 삽입된 `Trade` 리스트로 변경
- [x] import commit에서 `fresh_all = await list_trades(...)` 제거 및 메모리 append 적용
- [x] 회귀 테스트 추가
- [x] Backend test passes (`cd api && poetry run pytest tests/test_trades.py -q`)

## Risks / Open Questions

- Dynamic multi-row INSERT는 행 수가 매우 큰 단일 그룹에서 PostgreSQL 파라미터 제한에 가까워질 수 있다. 현재 거래내역서 임포트 규모에서는 낮은 위험으로 판단한다.
