# Spec: FastAPI trades + portfolio + 시세 (P2)

## 배경 / 문제

모바일앱 배포 후속 2단계 = **FastAPI 백엔드 분리**. P1a(스켈레톤+JWKS), P1b(accounts CRUD) 완료 상태. 이번 단계(P2)는 남은 10개 라우트 중 **trades 5 + portfolio 2 + stocks 2 = 7개 라우트**와 연관 순수 로직(`holdings`, `portfolio`, `quotes`, `realized-pnl`, `pnl-sync`, `validators/trade`)을 FastAPI로 포팅한다. 배포/컷오버는 범위 밖. analysis 3개 라우트(P3)는 별도 spec.

## 목표

- 7개 라우트의 FastAPI 등가 구현이 동작:
  - `GET /api/trades` (ticker/country 필터 + account join)
  - `POST /api/trades` (SELL oversell 검증 + `recalcGroupPnL`)
  - `GET /api/trades/{id}` (account join)
  - `PATCH /api/trades/{id}` (PnL 영향 필드 분기 + `validateMutation` + recalc)
  - `DELETE /api/trades/{id}` (`validateMutation(delete)` + recalc)
  - `GET /api/trades/{id}/summary` (SELL breakdown + FIFO holdingDays + strategyEval)
  - `GET /api/portfolio/holding` (account-scoped 수량 + WAC)
  - `GET /api/portfolio/summary` (positions + snapshots + totals + quotes)
  - `GET /api/stocks/quote` (KR 네이버 + US Yahoo)
  - `GET /api/stocks/search` (KR/US 자동완성)
- 에러 포맷 `{"error": "..."}` 유지, 상태 코드 등가 (201/204/400/401/404/500).
- 순수 로직은 pytest 단위 테스트, 라우트는 FakePool로 주요 경로 검증.
- 401 인증 실패 + RLS 격리(다른 유저 id로 접근 시 404).
- `poetry run pytest` 전체 통과, `ruff check` 통과, 로컬 `uvicorn` 기동 + curl 검증.

## 설계

### 접근 방식

1. **Pydantic 스키마** — `validators.ts`의 `TradeCreateSchema`/`TradeUpdateSchema`를 `schemas/trade.py`로 포팅. `commaPositive`/`commaNonNegative`는 `field_validator(mode="before")`로 재현(기존 `schemas/account.py` 패턴). PATCH 빈 body는 `model_fields_set`으로 판별.

2. **순수 로직** (`api/src/invest_note_api/domain/`):
   - `trade_types.py` — DB row 1:1 매핑 (`Trade` 모델, Decimal/datetime 필드)
   - `trade_utils.py` — `to_kst` (`zoneinfo`)
   - `holdings.py` — `compute_total_holding`, `compute_flexible_breakdown`, `compute_flexible_holding_days` (FIFO 가중평균), `find_latest_buy_strategy`, `compute_lot_quantity`
   - `realized_pnl.py` — `TradeGroupKey`, `sort_for_calc` (동순위 BUY 먼저), `compute_group_pnl`, `validate_mutation` (insert/update/delete), `build_pnl_map`
   - `portfolio.py` — `build_positions` (lot key: `ticker:country:accountId`), `merge_quotes`, `build_account_snapshots`, `build_totals`
   - 모두 DB 독립 순수 함수 (trades 리스트만 입력).

3. **시세 fetch** (`external/quotes.py`):
   - `httpx.AsyncClient` 기반 Naver/Yahoo 호출. 실패 시 조용히 `None` 반환.
   - **캐싱**: `cachetools.TTLCache(maxsize=512, ttl=60)` + `asyncio.Lock`. 의존성 `cachetools = "^5.3"` 추가.

4. **PnL 동기화 (`recalc_group_pnl`)** — **의도적 동작 변경**:
   - `db_ops/pnl_sync.py`: `compute_group_pnl` 결과를 `conn.executemany` 한 번으로 UPDATE.
   - ⚠️ Next.js는 병렬 개별 UPDATE + 실패 허용. FastAPI는 `executemany` → all-or-nothing, 실패 시 `APIError(500)` + 자동 ROLLBACK.
   - 근거: backlog "recalcGroupPnL 실패 플래그" + TOCTOU 부수 해결.

5. **한 트랜잭션 경계** — POST/PATCH/DELETE의 SELECT + validate + UPDATE/INSERT + recalc 모두 `acquire_for_user` 컨텍스트 내에서 실행.

6. **라우터 분리** — `routers/trades.py` (list/create/get/patch/delete/summary), `routers/portfolio.py` (holding/summary), `routers/stocks.py` (quote/search). `main.py`에 include.

7. **정규식/유니코드** — `hasKorean`: `re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]")`. ticker 화이트리스트 `[A-Za-z0-9.\-_가-힣]`.

### 주요 변경 파일

**신규**
- `api/src/invest_note_api/domain/{__init__,trade_types,trade_utils,holdings,realized_pnl,portfolio}.py`
- `api/src/invest_note_api/db_ops/{__init__,pnl_sync,trades_repo}.py`
- `api/src/invest_note_api/external/{__init__,quotes}.py`
- `api/src/invest_note_api/schemas/trade.py`
- `api/src/invest_note_api/routers/{trades,portfolio,stocks}.py`
- `api/tests/{test_trades,test_portfolio,test_stocks,test_holdings,test_realized_pnl,test_portfolio_logic}.py`

**수정**
- `api/src/invest_note_api/main.py` — 신규 라우터 3개 include
- `api/pyproject.toml` — `cachetools = "^5.3"` 추가 + `poetry lock --no-update`
- `api/README.md` — 10개 신규 endpoint curl 예시
- `api/tests/conftest.py` — FakePool 확장, quote fetch 모킹 fixture
- `api/tests/fake_pool.py` — trades 테이블 대응 (고정 응답 키-값 매칭)

### 재사용

- `auth/dependency.py` (`get_current_user`), `db.py` (`acquire_for_user`), `errors.py` (`APIError`)
- `schemas/account.py` — `field_validator(mode="before")` 패턴
- `routers/accounts.py` — 라우터 구조
- `tests/fake_pool.py` — 확장 기반

### 포팅 대상 원본 (Next.js)

- `app/src/app/api/trades/route.ts` (148줄)
- `app/src/app/api/trades/[id]/route.ts` (154줄)
- `app/src/app/api/trades/[id]/summary/route.ts` (77줄)
- `app/src/app/api/portfolio/holding/route.ts` (60줄)
- `app/src/app/api/portfolio/summary/route.ts` (58줄)
- `app/src/app/api/stocks/quote/route.ts` (39줄)
- `app/src/app/api/stocks/search/route.ts` (109줄)
- `app/src/lib/holdings.ts` (170줄)
- `app/src/lib/portfolio.ts` (285줄)
- `app/src/lib/quotes.ts` (108줄)
- `app/src/lib/trade-utils.ts` (29줄)
- `app/src/lib/analysis/realized-pnl.ts` (173줄)
- `app/src/lib/api-server/pnl-sync.ts` (26줄)
- `app/src/lib/api-server/validators.ts` (trade 부분 ~60줄)

## 구현 체크리스트

### 순수 로직 포팅 + 단위 테스트

- [x] `domain/trade_utils.py` — `to_kst` (zoneinfo)
- [x] `domain/trade_types.py` — `Trade` Pydantic 모델 (Decimal/datetime 필드)
- [x] `domain/realized_pnl.py` 포팅 + `tests/test_realized_pnl.py` 작성
- [x] `domain/holdings.py` 포팅 + `tests/test_holdings.py` 작성
- [x] `domain/portfolio.py` 포팅 + `tests/test_portfolio_logic.py` 작성

### DB 레이어 + 외부 fetch

- [x] `pyproject.toml` — `cachetools = "^5.3"` + `poetry lock --no-update`
- [x] `db_ops/trades_repo.py` — asyncpg SELECT/INSERT/UPDATE/DELETE 헬퍼
- [x] `db_ops/pnl_sync.py` — `recalc_group_pnl` 단일 executemany
- [x] `external/quotes.py` — httpx Naver/Yahoo + TTLCache(60s) + `fetch_quotes_by_keys`

### 스키마 + 라우터

- [x] `schemas/trade.py` — TradeCreate/TradeUpdate
- [x] `routers/trades.py` — 6 endpoint (5 CRUD + summary)
- [x] `routers/portfolio.py` — 2 endpoint
- [x] `routers/stocks.py` — 2 endpoint + 한글/종목코드 판별
- [x] `main.py` — 라우터 등록

### 테스트 + 검증

- [x] `tests/fake_pool.py` 확장, `tests/conftest.py` quote fixture 추가
- [x] `tests/test_trades.py` — list/create/get/patch/delete + oversell + 401/RLS
- [x] `tests/test_portfolio.py` — holding/summary + quote 실패 fallback
- [x] `tests/test_stocks.py` — quote(KR/US/mixed), search(한글/영문/6자리)
- [x] `poetry run pytest` 전체 통과 (101 passed)
- [x] `poetry run ruff check` 통과
- [ ] `uvicorn` 기동 + 10개 endpoint curl 검증 (실 JWT 필요 — 로컬에서 수동 진행)
- [x] `api/README.md` curl 예시 갱신

## 우려사항 / 리스크

- **Numeric 정밀도**: `numeric(14,2)` → `Decimal → float`. TS `number`(float64)와 동등. 저장 시 `Decimal` 복원.
- **시세 API 지연/차단**: httpx timeout 5s + 실패 시 `None`. TTLCache 60s로 rate-limit 완화.
- **FakePool 확장 부담**: 라우터 테스트는 쿼리 문자열 매칭 기반 고정 응답. 로직 커버리지는 순수 함수 단위 테스트로 보완.
- **USD/KRW 혼합 합산 버그**: `portfolio.ts:174` 부근 환율 미변환 합산 버그 — **동작 동치성 우선**, 포팅 시 그대로 유지. 별도 backlog.
- **`recalcGroupPnL` 동작 변경**: all-or-nothing → 한 row 실패 시 전체 500. 정합성↑/복원력↓ 수용.
- **배포 제외 확정**: Render/Railway, `api-client.ts` URL 변경, Next.js 라우트 제거는 범위 밖.
