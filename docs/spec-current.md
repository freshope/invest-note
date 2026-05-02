# Spec: BE simplify Round 2 — 응답 매핑 / 라우터 청소

## 배경 / 문제

`/simplify be 전체 조사` 결과에서 도출된 BE simplify 후속 항목 중 **Round 1** (`docs/spec-history/2026-05-01-be-simplify-round1-quick-wins.md`) 에서 처리한 3 개 (`model_copy` / `dataclasses.replace` / `sort_by_traded_at`) 외에 backlog (`docs/backlog.md` "BE simplify (Round 1 이후 deferred)" 섹션) 19 개가 남아있다.

Round 2 는 backlog 의 첫 번째 카테고리 **"응답 매핑 / 라우터 청소"** 5 개 항목 중 위험도 낮은 4 개를 묶는다 — 동작 변경 없음, 코드 중복 / 손-매핑 보일러플레이트만 제거. 5번째 항목 (`_trade_with_account_dict` → `TradeWithAccountResponse` 스키마 + `response_model` 위임) 은 LOC 중립 (현재 7줄 helper vs 신규 스키마 ~30줄 + camelCase 회피용 별도 BaseModel) 으로 판단되어 **미진행** 결정 — `docs/decisions.md` 에 근거를 기록하고 backlog 에서 제거한다.

이후 라운드 (효율 핫패스, 도메인 정리, 재사용 잔여) 는 별도 spec 으로 분리.

## 목표

- `routers/analysis.py` 의 `AnalysisDashboardResponse` 응답 빌드에서 31줄짜리 `summary` 손-매핑이 `asdict(summary)` 1줄로 대체된다
- `routers/portfolio._account_from_row` 의 UUID→str 변환 루프가 `account_row_to_dict` 헬퍼 안으로 흡수되어 호출지점이 단순해진다
- `routers/accounts.update_account` 의 SET-clause 손-빌드가 `db_ops/accounts_repo.patch_account` 헬퍼로 추출된다 (`patch_trade` 와 구조적으로 동형, signature 만 다름)
- `routers/trades.create_trade` 의 17줄 `Trade(...)` 매핑이 `**data.model_dump()` spread 로 단순화된다
- 모든 기존 테스트 (`api/tests/`) 가 그대로 통과한다 — 응답 wire format 동일, DB 동작 동일

## 설계

### 접근 방식

**1. `routers/analysis.py` — `summary` 응답 dict spread**

```python
from dataclasses import asdict

return AnalysisDashboardResponse.model_validate({
    "period": period_val,
    "summary": {"period": period_val, **asdict(summary)},
    "behavior": {...},
    "suggestions": {...},
})
```

`AnalysisSummary` dataclass 의 모든 필드명이 `AnalysisSummaryResponse` 와 동일해 `asdict` spread 가능. **`AnalysisSummary` 자체에 `period` 필드를 추가하지 않는다** — `period` 는 라우팅 관심사이지 도메인 사실이 아님.

**2. `routers/portfolio._account_from_row` → `account_row_to_dict` 흡수**

```python
# accounts_repo.py
def account_row_to_dict(row: Any) -> dict:
    d = dict(row)
    if "cash_balance" in d and d["cash_balance"] is not None:
        d["cash_balance"] = float(d["cash_balance"])
    for field in ("id", "user_id", "account_id"):
        if field in d and isinstance(d[field], UUID):
            d[field] = str(d[field])
    return d

# portfolio.py
def _account_from_row(row) -> Account:
    return Account(**account_row_to_dict(row))
```

**3. `routers/accounts.update_account` SET-clause → `accounts_repo.patch_account`**

```python
# db_ops/accounts_repo.py 신규
_UPDATABLE_COLS = frozenset({"name", "broker", "cash_balance"})
_RETURNING_COLS = "id, user_id, name, broker, cash_balance, created_at, updated_at"

async def patch_account(conn: Any, account_id: UUID, patch: dict) -> dict | None:
    safe_patch = {k: v for k, v in patch.items() if k in _UPDATABLE_COLS}
    if not safe_patch:
        return None

    set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(safe_patch))
    row = await conn.fetchrow(
        f"UPDATE accounts SET {set_clause}, updated_at = now()"
        f" WHERE id = $1 RETURNING {_RETURNING_COLS}",
        account_id,
        *safe_patch.values(),
    )
    return account_row_to_dict(row) if row else None
```

`patch_trade` 와의 차이 (의도적 비대칭): `patch_trade` 는 `bool`, `patch_account` 는 `dict | None` (응답에 row 필요). 라우터의 빈 fields 사전 체크는 유지 (DB round-trip 회피).

**4. `routers/trades.create_trade` `Trade(...)` 17줄 → `**data.model_dump()` spread**

```python
new_trade = Trade(
    id="__new__",
    user_id=str(user.id),
    total_amount=data.price * data.quantity,
    created_at=now,
    updated_at=now,
    **data.model_dump(),
)
```

`TradeCreate` 필드명이 모두 `Trade` 의 부분집합 — keyword 충돌 없음. `data.country_code or DEFAULT_COUNTRY` / `data.exchange or ""` 은 schema 기본값 + validator 가 차단해 dead branch.

### 주요 변경 파일

- `api/src/invest_note_api/routers/analysis.py` — `summary` 손-매핑 13줄을 `asdict(summary)` spread 로 교체
- `api/src/invest_note_api/routers/portfolio.py` — `_account_from_row` 의 UUID 변환 루프 삭제
- `api/src/invest_note_api/db_ops/accounts_repo.py` — `account_row_to_dict` UUID→str 변환 추가, `patch_account` 신규 + 상수 이동
- `api/src/invest_note_api/routers/accounts.py` — `update_account` 가 `patch_account` 호출로 위임
- `api/src/invest_note_api/routers/trades.py` — `create_trade` 의 `Trade(...)` 17줄 spread 단순화

## 구현 체크리스트

- [ ] `db_ops/accounts_repo.py` — `account_row_to_dict` 에 UUID 필드 변환 추가 (`id`, `user_id`, `account_id`)
- [ ] `db_ops/accounts_repo.py` — `_UPDATABLE_COLS` / `_RETURNING_COLS` 상수 + `patch_account(conn, account_id, patch) -> dict | None` 신규
- [ ] `routers/portfolio.py` — `_account_from_row` 의 UUID 변환 for-loop 삭제
- [ ] `routers/accounts.py` — `update_account` 가 `patch_account` 호출로 위임
- [ ] `routers/analysis.py` — `summary` 손-매핑 13줄 → `{"period": period_val, **asdict(summary)}`
- [ ] `routers/trades.py` — `create_trade` 의 `Trade(...)` 17줄을 `**data.model_dump()` spread 로 단순화
- [ ] 테스트 통과: `cd api && poetry run pytest -q`
- [ ] `docs/decisions.md` 에 Item 3 (`_trade_with_account_dict` → `TradeWithAccountResponse`) 미진행 결정 기록
- [ ] `docs/backlog.md` "응답 매핑 / 라우터 청소" 섹션에서 Item 3 줄 제거

## 우려사항 / 리스크

- **Item 1 (`asdict` spread)** — `AnalysisSummary` ↔ `AnalysisSummaryResponse` 필드명 1:1 매핑 의존. 향후 한쪽 필드명 변경 시 silent break — 변경 시 양쪽 동시 수정 책임은 기존과 동일.
- **Item 2 (`account_row_to_dict` UUID 흡수)** — wire format 무변화 검증 책임. `accounts.list_accounts` / `create_account` 응답이 dict 단계에서 UUID 객체였다면 FastAPI 가 자동 str 화했지만, 이제 dict 안에서 이미 str. 기존 테스트가 응답 형식 검증해야 함.
- **Item 3 (미진행 확정)** — LOC 중립 + FE snake_case 계약 보존 비용 → `decisions.md` 에 근거 기록 (2026-04-30 Tier 3 결정과 동일 패턴).
- **Item 4 (`patch_account` 비대칭)** — `patch_trade` 와 signature 다름 (`dict | None` vs `bool`). 도메인 시맨틱 차이 (계좌 응답은 row 필요).
- **Item 5 (`**data.model_dump()` spread)** — `TradeCreate.country_code` / `exchange` dead branch 제거가 안전한 근거: 스키마 기본값 + validator 가 차단. schema 기본값 변경 시 라우터도 함께 봐야 함.

## 검증 방법

```bash
cd api && poetry run pytest -q
```

핵심 테스트 그룹:
- `tests/test_analysis_logic.py` / `tests/test_analysis_router.py` — `AnalysisDashboardResponse` 직렬화
- `tests/test_accounts.py` — `list_accounts` / `update_account` 응답 dict, UUID→str wire format
- `tests/test_portfolio_router.py` — `_account_from_row` 흐름
- `tests/test_trades_router.py` — `create_trade` 응답 + DB 저장값
- `tests/test_pnl_sync.py` — create_trade → recalc_group_pnl 흐름

## 후속 라운드 (이번 spec 범위 밖)

- Round 3 — 효율 핫패스 (`httpx.AsyncClient` lifespan, broker parser threadpool, period SQL push)
- Round 4 — 도메인 정리 (`compute_holding_summary` walker 통합, `build_positions` 분리)
- Round 5+ — 페이지네이션, `accounts_repo.list_accounts` 헬퍼 추출, `make_signature` ↔ `make_preview_signature` 통합
