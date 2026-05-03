# Spec: BE simplify Round 3 — 효율 / 핫패스

## 배경 / 문제

`docs/backlog.md` 의 "BE simplify (Round 1 이후 deferred)" 섹션에는 Round 1·2 처리 외에 15개 항목이 3개 카테고리(효율/핫패스 6, 도메인 정리 2, 재사용/잔여 7) 로 남아있다. backlog 자체가 "위험도/가치 평가 후 Round 3+ 에서 분할 처리" 를 명시한다.

Round 3 는 backlog 의 **"효율 / 핫패스"** 카테고리에서 **FE 협조가 필요 없는 4개 항목** 만 묶는다 — 동작 변경 없음, 라우터 / 외부 클라이언트의 hot-path 비효율 제거. 6개 중:
- 1개 (`GET /api/trades` 페이지네이션) 는 backlog 가 명시적으로 "FE backlog `tradesApi.list()` 와 동반" 이라고 표기 → Round 4 (BE+FE 동시) 로 분리.
- 1개 (`routers/analysis period 파라미터 SQL push`) 는 코드 검토 결과 `all_trades` 가 `build_positions` / `compute_concentration` / `build_strategy_evaluations` 에 의도적 전체 거래로 입력되고 있어 (line 100 주석 명시), SQL push 가 1회 fetch 를 2회 (전체 + period-filtered) 로 만드는 net-negative 변경 → **미진행** 결정. `docs/decisions.md` 에 근거 기록.

이후 라운드 (도메인 정리, 재사용 잔여) 는 별도 spec 으로 분리.

## 목표

- `httpx.AsyncClient` 가 `external/quotes.py` / `external/naver_search.py` / `broker_import/ticker_resolver.py` 3 곳에서 매 요청 신규 생성되지 않고, FastAPI lifespan 에서 단일 인스턴스를 공유한다 (connection pool 재사용)
- broker parser (`pdfplumber` / `openpyxl` 동기 호출) 가 async 라우터 이벤트 루프를 차단하지 않는다 — `run_in_threadpool` 래핑
- `import_preview` 가 사용자 전체 trades 를 fetch 하지 않고, 파싱된 거래의 날짜 범위로 좁혀 fetch 한다 (서명 dup 검사용)
- `routers/accounts.delete_account` 가 `count` + `delete` 두 round-trip 을 단일 SQL 로 통합한다
- 모든 기존 테스트 (`api/tests/`) 가 그대로 통과하고, 응답 wire format / DB 동작이 동일하다

## 설계

### 접근 방식

**1. `httpx.AsyncClient` lifespan 공유 (3 callsite + main.py)**

`main.py` 의 lifespan handler 에서 `app.state.http_client = httpx.AsyncClient(timeout=...)` 단일 인스턴스 생성, 종료 시 `await client.aclose()`. 3 callsite (`external/quotes.py`, `external/naver_search.py`, `broker_import/ticker_resolver.py`) 는 라우터에서 client 를 주입받아 호출 (`async def fn(..., *, client: httpx.AsyncClient)`). 각 callsite 의 `async with httpx.AsyncClient() as client:` 블록 제거.

호출자 (라우터) 는 `request.app.state.http_client` 또는 FastAPI Depends 로 주입. **공유 client 는 callsite 에서 close 하지 않는다** (lifespan 책임).

**2. broker parser threadpool 화 (`routers/trades.py:340` import_preview)**

```python
from fastapi.concurrency import run_in_threadpool
parse_result = await run_in_threadpool(parser.parse, file_bytes, filename)
```

parser 자체 (`broker_import/samsung_xlsx.py`, `broker_import/toss_pdf.py`) 코드는 무수정 — 호출 라인만 래핑.

**3. `import_preview` — `list_trades(...)` 시그니처에 date 범위 옵션 추가**

`db_ops/trades_repo.py` 의 `list_trades(conn, user_id)` 를 키워드 옵션으로 확장 (기존 ORDER BY DESC, `user_id: str` 시그니처 유지):

```python
async def list_trades(
    conn: Any,
    user_id: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Trade]:
    where = ["user_id = $1"]
    params: list[Any] = [user_id]
    if date_from is not None:
        where.append(f"traded_at >= ${len(params) + 1}")
        params.append(date_from)
    if date_to is not None:
        where.append(f"traded_at <= ${len(params) + 1}")
        params.append(date_to)
    rows = await conn.fetch(
        f"SELECT * FROM trades WHERE {' AND '.join(where)} ORDER BY traded_at DESC",
        *params,
    )
    return [_row_to_trade(r) for r in rows]
```

기본값 `None` 이라 기존 호출자 전부 무영향.

**3 적용 (import_preview):** `routers/trades.py:352` 의 `all_trades = await list_trades(conn, user.id)` 를, 파싱 결과(`parsed_trades`) 의 min/max `traded_at_kst` 을 먼저 계산한 뒤 KST→UTC 변환해 `list_trades(conn, user.id, date_from=min_dt, date_to=max_dt)` 로 좁힌다. 빈 파싱 결과 (이미 빠른 fail 경로) 는 호출 자체 회피.

**dup signature 검증의 정확성:** preview signature 는 `(date, ticker, asset_name, side, qty, price)` 기반 (`make_preview_signature`). 동일 키가 다른 날짜에 존재할 수 없으므로, 파싱 거래의 날짜 범위 외 행은 dup 후보가 될 수 없음 — 의미 보존됨.

**4. `routers/accounts.delete_account` round-trip 통합**

`DELETE FROM accounts WHERE id = $1 AND NOT EXISTS (SELECT 1 FROM trades WHERE account_id = $1) RETURNING id` 한 번의 호출로:
- row 반환 → 삭제 성공 (200)
- row 없음 → `SELECT EXISTS (account)` 1회로 분기:
  - account 없음 → 404
  - account 있음 → trades 가 있다는 의미 → 409 + count 메시지 (count 가 필요한 경우만 추가 SELECT)

UI 가 trade count 메시지를 정확한 수치로 보여주는지 확인 — 단순 "거래 내역이 있어 삭제 불가" 메시지면 count 쿼리 자체가 불필요. 현 메시지가 count 포함이면, 실패 path 에서만 count 1회 (성공 path 에서 절약).

### 주요 변경 파일

- `api/src/invest_note_api/main.py` — lifespan 에 `app.state.http_client` 추가 / 종료 시 close
- `api/src/invest_note_api/external/quotes.py` — `async with httpx.AsyncClient()` 제거, client 주입
- `api/src/invest_note_api/external/naver_search.py` — `client=None` fallback 제거 (모든 호출자가 항상 client 전달)
- `api/src/invest_note_api/broker_import/ticker_resolver.py` — `client` 인자를 받도록 변경
- `api/src/invest_note_api/routers/trades.py` — `import_preview` 의 `parser.parse` `run_in_threadpool` 래핑 + `list_trades(date_from, date_to)` 호출 + `resolve_tickers` 에 client 전달
- `api/src/invest_note_api/routers/stocks.py` — `search_kr` 호출 시 client 전달
- `api/src/invest_note_api/routers/portfolio.py` — `fetch_quotes_by_keys` 호출 경로에 client 전달 (필요 시)
- `api/src/invest_note_api/routers/analysis.py` — `fetch_quotes_by_keys` 호출 경로에 client 전달 (필요 시)
- `api/src/invest_note_api/db_ops/trades_repo.py` — `list_trades` 시그니처에 `date_from` / `date_to` 키워드 옵션 추가
- `api/src/invest_note_api/routers/accounts.py` — `delete_account` 의 `count` + `delete` 통합 SQL
- `docs/decisions.md` — Item 5 (analysis period SQL push) 미진행 결정 기록
- `docs/backlog.md` — 처리한 4 개 항목 + Item 5 미진행 결정 반영

### 재사용할 기존 유틸

- `fastapi.concurrency.run_in_threadpool` (FastAPI 내장)
- `domain/analysis/period.py:period_to_range` (이미 존재 — date range 계산)
- `db_ops/trades_repo.list_trades` (확장 대상)

## 구현 체크리스트

### 사전 — 문서 동기화
- [ ] `docs/decisions.md` 에 Item 5 (analysis period SQL push) 미진행 결정 기록
- [ ] `docs/backlog.md` "효율 / 핫패스" 섹션에서 Item 5 줄 제거 (decisions.md 참조)
- [ ] `docs/spec-current.md` 도 본 plan 내용으로 동기화

### Item 1 — httpx 공유 client
- [ ] `main.py` — lifespan 에 `app.state.http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)` 추가, 종료 시 `aclose()`
- [ ] `external/http_client.py` 신규 — `create_http_client()` + `get_http_client(request)` Depends helper
- [ ] `external/quotes.py` — `fetch_quotes_by_keys(state, keys, *, client)` 시그니처로 client 받음 (필수), 내부 `async with httpx.AsyncClient()` 제거
- [ ] `external/naver_search.py` — 이미 `client` 키워드 옵션 받음. `client=None` fallback 은 단위 테스트 호환성을 위해 유지 (production 라우터는 항상 client 전달)
- [ ] `broker_import/ticker_resolver.py` — `resolve_tickers(asset_names, ticker_hints, *, client)` 시그니처로 client 받음. 호환을 위해 `client=None` fallback 유지 (라우터 production 경로는 항상 client 전달)
- [ ] 라우터들 (`routers/trades.py`, `routers/stocks.py`, `routers/portfolio.py`, `routers/analysis.py`) — `Depends(get_http_client)` 로 주입해 호출 함수에 전달

### Item 2 — broker parser threadpool
- [ ] `routers/trades.py:340` — `parse_result = await run_in_threadpool(parser.parse, file_bytes, filename)` 래핑

### Item 4 — list_trades date 범위 옵션 (import_preview 적용)
- [ ] `db_ops/trades_repo.py` — `list_trades` 에 `*, date_from: datetime | None = None, date_to: datetime | None = None` 키워드 옵션 추가, ORDER BY DESC 유지
- [ ] `routers/trades.py:352` `import_preview` — 파싱 결과의 KST 일자 min/max 계산 → `kst_date_to_utc` 로 UTC 변환 → `list_trades(date_from=min_dt, date_to=max_dt)` 로 호출. 빈 파싱 결과는 호출 자체 회피
- [ ] 빈 파싱 결과/모두 ticker 미해결 시 `existing_sigs` 가 빈 셋이어도 동작 동일함 확인

### Item 6 — delete_account round-trip 통합
- [ ] `routers/accounts.delete_account` — `DELETE FROM accounts WHERE id = $1 AND user_id = $2 AND NOT EXISTS (SELECT 1 FROM trades WHERE account_id = $1) RETURNING id` 통합. row 없을 때 분기: account 미존재 → 404, 거래 잔존 → 409

### 검증
- [ ] 타입 체크: 프로젝트 표준 명령 (확인 후 `mypy` / `ruff` / 기타)
- [ ] 테스트 통과: `cd api && poetry run pytest -q`
- [ ] 핵심 회귀 케이스 점검: `tests/test_trades_router.py` (import_preview), `tests/test_accounts.py` (delete 분기), `tests/test_quotes*.py` / `tests/test_stocks*.py` (공유 client)

### 마무리 (spec-finish 시 처리)
- [ ] `docs/backlog.md` "효율 / 핫패스" 섹션에서 처리된 4 개 항목 제거 + Round 4 (페이지네이션, FE 협조) 메모 유지
- [ ] `docs/spec-current.md` → `docs/spec-history/2026-05-03-be-simplify-round3-hot-path.md` 이동

## 우려사항 / 리스크

- **httpx 공유 client (Item 1)** — 동시성 안전: `httpx.AsyncClient` 는 thread-safe / async-safe 하지만, **callsite 가 `aclose()` 를 호출하면 안 됨** (lifespan 책임). connection pool 한계 (`limits=httpx.Limits(...)`) 설정 검토 — 기본값으로 충분한지 확인 필요. 외부 API 호출 fan-out 이 갑자기 늘어나는 시나리오 (분석 탭 동시 fetch 등) 에서 단일 client 가 bottleneck 이 될 수 있는지 확인.
- **broker parser threadpool (Item 2)** — `run_in_threadpool` 은 starlette 기본 threadpool 사용. 동시 import 요청이 많을 때 thread 고갈 위험은 있으나, 현 트래픽 (개인 사용자) 에서는 무시 가능. 효과 검증: 이전에 import 중 다른 라우터 응답이 지연되었는지 (anecdotal) 확인.
- **`list_trades` 시그니처 변경 (Item 4)** — 기존 호출자 (`routers/analysis` / `routers/trades` 외 import_preview) 가 새 키워드 옵션을 사용하지 않아도 동작 동일 (default `None` → WHERE 절 미추가). 마이그레이션 비파괴.
- **`delete_account` 통합 SQL (Item 6)** — `NOT EXISTS` 서브쿼리는 `accounts.id` PK 인덱스 + `trades.account_id` 인덱스 필요 (이미 있을 것). RLS 가 `accounts` / `trades` 양쪽에 걸려있어 단일 쿼리에서도 user 격리 보존되는지 확인 — `WHERE id = $1 AND user_id = $2` 명시 추가 권장 (RLS 가 이미 격리하지만 일관성).
- **wire format 무변화** — 이번 라운드는 동작/응답 변경 없음. 모든 변경은 hot-path 효율 / 코드 단순화.
- **테스트만으로 충분하지 않은 검증 영역** — Item 1 (공유 client), Item 2 (threadpool) 는 perf-shape 변경. 단위 테스트는 회귀 (regression) 만 검증하고, 의도된 효과 (connection 재사용, 이벤트 루프 비차단) 는 자동 검증되지 않음. 수동 확인 (로그·METRICS 또는 코드 리뷰) 으로 보완.

## 검증 방법

```bash
cd api && poetry run pytest -q
cd api && poetry run mypy src  # 또는 프로젝트 표준
```

핵심 테스트 그룹:
- `tests/test_trades_router.py` — `import_preview` dup 검출 정상, `list_trades(date_from, date_to)` 정확성
- `tests/test_accounts.py` — `delete_account` 성공·실패 분기 (404 / 409)
- `tests/test_quotes*.py` / `tests/test_stocks*.py` (있다면) — 공유 client 패턴에서 fetch 정상
- 통합 테스트 — broker parser import 가 다른 요청을 차단하지 않는지 (자동 검증 어려우면 코드 리뷰)

## 후속 라운드 (이번 spec 범위 밖)

- **Round 4 — `GET /api/trades` 페이지네이션 + `ticker` 필터 SQL push** — backlog 가 "FE backlog `tradesApi.list()` 와 동반" 명시. BE+FE 동시 변경 필요해 본 라운드 제외.
- **Round 5 — 도메인 정리** (`compute_holding_summary` walker 통합, `build_positions` 분리)
- **Round 6+ — 재사용 / 잔여** (`accounts_repo.list_accounts` 헬퍼, `make_signature` 통합, `_holding_bucket` Counter 화, `_decimal_to_float*` 통합, `EMOTION_UNTAGGED` Literal, `SellBreakdown.is_manual_input` 폐기, `_parse_*_price` 통합)
- **Item 5 (analysis period SQL push) 미진행 확정** — `docs/decisions.md` 참조
