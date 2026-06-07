# Spec: BE simplify Tier 3 Round 3 — 모듈 글로벌 → app.state 이전

> 완료: 2026-04-30

## 배경 / 문제

`api/external/quotes.py` 의 `_cache` / `_cache_lock` / `_inflight` 와 `routers/trades.py` 의 `_STAGING` 이 모듈-레벨 mutable global 로 남아 있다. 테스트는 autouse fixture 로 `quotes._cache.clear()` 하거나 `trades._STAGING[...] = ...` 로 직접 주입해 격리를 흉내내는 anti-pattern 을 사용 중. Round 2 (`docs/issue-history/2026-04-30-be-simplify-tier3-round2.md`) 에서 명시적으로 Round 3 로 분리됐다 (항목 H).

본 라운드의 목표는 **테스트 격리 + DI 청결성**. `app.state` 는 프로세스별 상태이므로 진정한 멀티 워커 정합성(특히 staging) 은 본 라운드에서 해결하지 않으며, backlog "Preview staging 멀티 워커 대응" 항목으로 분리 유지.

## 목표

- `external/quotes.py` 의 모듈-레벨 `_cache` / `_cache_lock` / `_inflight` 가 사라지고 `app.state.quote_cache: QuoteCacheState` 로 이전된다.
- `routers/trades.py` 의 모듈-레벨 `_STAGING` 이 사라지고 `app.state.trade_staging: TradeStagingState` 로 이전된다.
- 호출자 라우터(stocks/portfolio/analysis/trades) 가 `Depends(...)` 로 상태를 주입받는다.
- `tests/test_quotes.py` 와 `tests/test_trades.py::test_commit_fetches_per_group` 가 모듈 globals 를 직접 만지지 않는다.
- 동작 변경 없음 (TTL=60s, maxsize=512 / TTL=600s, maxsize=256 그대로).
- `cd api && poetry run pytest -q` 가 그린.

## 설계

### 접근 방식

기존 패턴(`db.py:17` 의 `get_pool` + `app.state.pool`) 을 그대로 따른다.

**1. 상태 컨테이너는 `@dataclass`** — 프로젝트 컨벤션. `field(default_factory=...)` 로 mutable default 처리.

```python
# external/quotes.py
@dataclass
class QuoteCacheState:
    cache: TTLCache[str, dict | None] = field(
        default_factory=lambda: TTLCache(maxsize=QUOTE_CACHE_MAXSIZE, ttl=QUOTE_CACHE_TTL)
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    inflight: dict[str, asyncio.Future] = field(default_factory=dict)
```

```python
# routers/trades.py
@dataclass
class TradeStagingState:
    cache: cachetools.TTLCache = field(
        default_factory=lambda: cachetools.TTLCache(maxsize=256, ttl=600)
    )
```

**2. dependency 함수는 도메인 모듈에 공동 배치** — 캐시/스테이징은 도메인 책임이므로 같은 파일에 둔다.

```python
# external/quotes.py
def get_quote_cache_state(request: Request) -> QuoteCacheState:
    return request.app.state.quote_cache

# routers/trades.py
def get_trade_staging_state(request: Request) -> TradeStagingState:
    return request.app.state.trade_staging
```

**3. `_get_cached` / `fetch_quotes_by_keys` 시그니처 변경** — state 를 첫 인자로 받는다. 모듈-레벨 globals 삭제.

```python
async def _get_cached(state: QuoteCacheState, key: str, fetch_fn) -> dict | None: ...
async def fetch_quotes_by_keys(state: QuoteCacheState, keys: list[str]) -> dict[str, QuoteResult | None]: ...
```

**4. lifespan 초기화** — `database_url` 분기와 무관하게 항상 두 state 를 만든다.

**5. 테스트 인프라**
- `test_quotes.py` 는 함수-스코프 `quote_state` 픽스처에서 `QuoteCacheState()` 직접 인스턴스화. autouse `clear_cache` 픽스처 제거.
- `tests/conftest.py::trades_client` 를 `with TestClient(app) as c: yield c` 형태로 변경해 lifespan 이 트리거되도록 한다.
- `test_trades.py::test_commit_fetches_per_group` 는 `trades_client.app.state.trade_staging.cache[staging_id] = {...}` 로 시드.

### 주요 변경 파일

- `api/src/invest_note_api/external/quotes.py` — `QuoteCacheState`, `get_quote_cache_state` 추가, 시그니처 변경, globals 삭제
- `api/src/invest_note_api/routers/trades.py` — `TradeStagingState`, `get_trade_staging_state` 추가, DI 적용, `_STAGING` 삭제
- `api/src/invest_note_api/routers/stocks.py` — `Depends(get_quote_cache_state)` 추가
- `api/src/invest_note_api/routers/portfolio.py` — 동일
- `api/src/invest_note_api/routers/analysis.py` — 동일
- `api/src/invest_note_api/main.py` — lifespan 에서 두 state 초기화
- `api/tests/conftest.py` — `trades_client` 를 `with TestClient` 로 변경
- `api/tests/test_quotes.py` — 픽스처 재작성, 호출부 갱신
- `api/tests/test_trades.py` — `test_commit_fetches_per_group` 시드 방식 변경
- `docs/backlog.md` — Tier 3 항목 제거 (완료 시점)

## 구현 체크리스트

- [x] `external/quotes.py` 에 `QuoteCacheState` + `get_quote_cache_state` 추가, `_get_cached`/`fetch_quotes_by_keys` 시그니처 state-first, 모듈 globals 삭제
- [x] `routers/stocks.py` / `routers/portfolio.py` / `routers/analysis.py` 호출자에 `Depends(get_quote_cache_state)` 추가
- [x] `routers/trades.py` 에 `TradeStagingState` + `get_trade_staging_state` 추가, `import_preview` / `import_commit` DI 적용, `_STAGING` 삭제
- [x] `main.py` lifespan 에서 `app.state.quote_cache` / `app.state.trade_staging` 초기화
- [x] `tests/conftest.py` 의 `trades_client` 를 `with TestClient(app) as c: yield c` 로 변경
- [x] `tests/test_quotes.py` 재작성 (autouse 제거, 함수 스코프 픽스처 도입)
- [x] `tests/test_trades.py::test_commit_fetches_per_group` 시드를 `client.app.state.trade_staging.cache[...]` 로 교체
- [x] `cd api && poetry run pytest -q` 전체 그린
- [x] `docs/backlog.md` 의 BE simplify Tier 3 항목 정리

## 우려사항 / 리스크

1. **`trades_client` 픽스처 변경 파급** — `with TestClient(app)` 으로 lifespan 매 테스트 실행. `database_url` 빈 분기에서 풀 생성 비용 없음 (`main.py:27-30`). 동일 픽스처 사용 테스트 회귀 검증 필수.
2. **`test_quotes.py` 의 직접 호출** — `_get_cached` 시그니처 변경으로 호출부 전부 수정.
3. **순환 import 위험 없음** — `main.py` 가 이미 `routers.trades` import 중.
4. **멀티 워커 한계** — 본 라운드 범위 밖, backlog 별도 항목 유지.
5. **lambda 클로저** — `_fetch_kr_price` 캡처 패턴 그대로 유지.

## 검증

```bash
cd api && poetry run pytest tests/test_quotes.py -v
cd api && poetry run pytest tests/test_trades.py::TestImportCommit -v
cd api && poetry run pytest -q
grep -rn "_STAGING\|quotes\._cache\|quotes\._inflight\|quotes\._cache_lock" api/src api/tests
```

마지막 grep 결과는 비어 있어야 한다 (테스트 신규 픽스처 제외).
