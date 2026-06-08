# Spec: BE simplify Round 1 — quick wins (model_copy, dataclasses.replace, 정렬 헬퍼 통합)

> 완료: 2026-05-01

## 배경 / 문제

`/simplify be 전체 조사` 결과 백엔드 (~58 파일, ~4900 LOC) 에서 다수의 정리 후보가 나왔다. FE simplify 와 같이 작은 라운드로 분할 진행하기로 결정했다.

Round 1 은 **위험도 가장 낮은 3 개 항목** 만 묶는다 — 동작 변경 없음, 타입 안전성/가독성만 개선. 이후 라운드(응답 매핑 청소, httpx lifespan 공유, 도메인 walker 통합 등)는 별도 spec 으로 분리.

## 목표

- `Trade` 가상 patch 적용이 Pydantic v2 표준 `model_copy(update=)` 패턴을 사용한다
- `Position` quote 머지가 `dataclasses.replace` 로 타입-세이프하게 동작한다
- `traded_at` 단순 오름차순 정렬 헬퍼가 `domain/trade_utils.py` 한 곳에서 export 되어 `holdings.py` / `portfolio.py` 가 공유한다
- `pnl_sync` / 분석 / 포트폴리오 / oversell 검증 등 기존 동작·테스트 결과는 변하지 않는다 (정렬 키 동일, virtual patch 결과 동일, merged Position 필드 동일)

## 설계

### 접근 방식

**1. `_apply_virtual` → `Trade.model_copy(update=)`**

현재 (`domain/realized_pnl.py:166-178`):

```python
if mutation_type == "update":
    patched_data = {**trade.model_dump(), **(patch or {})}
    patched = Trade(**patched_data)
    return [patched if t.id == trade.id else t for t in trades]
```

→

```python
if mutation_type == "update":
    patched = trade.model_copy(update=patch or {})
    return [patched if t.id == trade.id else t for t in trades]
```

`model_copy` 는 v2 권장 API. `model_dump → Trade(**...)` 는 전체 재검증이 일어나는데 patched data 는 이미 검증된 Trade 라 불필요. `Trade` 모델은 이미 다른 곳(`routers/trades.py:202, 284`) 에서 `model_copy` 를 사용 중이라 일관성도 ↑.

**2. `merge_quotes` → `dataclasses.replace`**

현재 (`domain/portfolio.py:228-244`):

```python
result.append(Position(
    **{
        **pos.__dict__,
        "current_price": quote["price"],
        "evaluation": evaluation,
        "unrealized_pnl": evaluation - pos.cost_basis,
    }
))
```

→

```python
from dataclasses import replace  # 모듈 상단 추가
...
result.append(replace(
    pos,
    current_price=quote["price"],
    evaluation=evaluation,
    unrealized_pnl=evaluation - pos.cost_basis,
))
```

`Position` 은 dataclass. `__dict__` spread 는 frozen=False 만 보장되고 타입 검사도 우회. `dataclasses.replace` 는 모든 필드 키워드 검증 + IDE 친화적.

**3. `_sort_by_traded_at` / `_by_traded_at` → `domain/trade_utils.py:sort_by_traded_at`**

두 곳에 동일한 본문이 있다:
- `domain/holdings.py:35-36 _sort_by_traded_at`
- `domain/portfolio.py:103-104 _by_traded_at`

본문은 정확히 같다 — `sorted(trades, key=lambda t: t.traded_at)`.

**조치**: `domain/trade_utils.py` 에 `sort_by_traded_at` public helper 추가 → 위 두 곳을 import 로 치환, 로컬 함수 정의 삭제.

**중요**: `domain/realized_pnl.py:60 sort_for_calc` 는 BUY-first / created_at tiebreak 를 추가한 *다른* 함수이므로 통합 대상 아님.

테스트 파일 `api/tests/test_trade_walker.py:55` 의 로컬 `_by_traded_at` 도 의도된 테스트 헬퍼이므로 건드리지 않는다.

### 주요 변경 파일

- `api/src/invest_note_api/domain/realized_pnl.py` — `_apply_virtual` update 분기 1 줄 교체 (~4 줄 → 2 줄)
- `api/src/invest_note_api/domain/portfolio.py` — `merge_quotes` 의 `__dict__` spread 를 `dataclasses.replace` 로 교체 + 모듈 상단 `from dataclasses import replace` 추가, `_by_traded_at` 로컬 함수 삭제 후 `from .trade_utils import sort_by_traded_at` 사용
- `api/src/invest_note_api/domain/holdings.py` — `_sort_by_traded_at` 로컬 함수 삭제 후 `from invest_note_api.domain.trade_utils import sort_by_traded_at` 사용
- `api/src/invest_note_api/domain/trade_utils.py` — `sort_by_traded_at(trades) -> list[Trade]` public helper 신규 추가

## 구현 체크리스트

- [x] `domain/trade_utils.py` 에 `sort_by_traded_at` 헬퍼 추가 (TYPE_CHECKING 기반 Trade import)
- [x] `domain/holdings.py` — 로컬 `_sort_by_traded_at` 삭제, `sort_by_traded_at` import 후 `compute_holding_summary` 에서 사용
- [x] `domain/portfolio.py` — 로컬 `_by_traded_at` 삭제, `sort_by_traded_at` import 후 `build_positions` 의 walker 호출에서 사용 (실제 호출 1곳)
- [x] `domain/portfolio.py` — `from dataclasses import replace` 추가, `merge_quotes` 의 `__dict__` spread 를 `replace(pos, ...)` 로 교체
- [x] `domain/realized_pnl.py` — `_apply_virtual` update 분기를 `trade.model_copy(update=patch or {})` 로 교체
- [x] 테스트 통과: `cd api && poetry run pytest -q` → 251 passed

## 우려사항 / 리스크

- **정렬 헬퍼 통합 시 의미 변화 없음 검증 완료** — 두 함수 본문 100% 동일. `sort_for_calc` 와 혼동되지 않도록 이름은 `sort_by_traded_at` (단순 ASC 의도 명시).
- **`model_copy` 검증 동작** — Pydantic v2 의 `model_copy(update=)` 는 기본적으로 **재검증을 하지 않는다** (성능 의도). 기존 `Trade(**patched_data)` 는 재검증을 했지만, `_apply_virtual` 호출자는 검증된 `Trade` 인스턴스 + 부분 patch dict 를 넘기므로 의미 변화 없음. oversell 검증(`validate_mutation`) 은 patched 의 quantity/price 만 walker 가 다시 사용 — 모델 검증 무관.
- **`dataclasses.replace`** — `Position` 은 `@dataclass` 로 명시되어 있고 frozen 아님 (현재 `__dict__` spread 가 동작하는 이유). `replace` 는 동등 동작 + 타입 검사.
- **호출 사이트 수**: `_by_traded_at` 은 portfolio.py 안 2곳, `_sort_by_traded_at` 은 holdings.py 안 1곳 — 모두 단일 모듈 내부. import 변경 영향 범위 좁음.
- **외부 사용처 없음**: 두 헬퍼 모두 `_` prefix private. grep 결과 production 코드 외부 사용 없음.

## 검증 방법

```bash
cd api && poetry run pytest -q
```

핵심 테스트 그룹 (모두 기존 테스트, 신규 테스트 추가 불필요):
- `test_realized_pnl.py` — `validate_mutation` (insert/update/delete 가상 적용)
- `test_portfolio_logic.py` — `merge_quotes` (quote 있/없 두 분기)
- `test_holdings.py` — `compute_holding_summary` 정렬 동작
- `test_trade_walker.py` — walker sort_fn 인자로 헬퍼 변경 후에도 통과
- `test_pnl_sync.py` — virtual mutation 의 PnL 결과 동일성

mypy/타입 체크는 백엔드는 별도 설정 없으므로 pytest 통과로 갈음.

## 후속 라운드 (이번 spec 범위 밖)

Round 2 ~ 5+ 는 별도 spec 에서 진행:
- Round 2 — 응답 매핑 청소 (`routers/analysis.py` 31줄, `_account_from_row` 누수, `TradeWithAccountResponse` 스키마화)
- Round 3 — 효율 핫패스 (`httpx.AsyncClient` lifespan 공유, broker parser threadpool 화)
- Round 4 — 도메인 정리 (`compute_holding_summary` walker 통합, `build_positions` 분리)
- Round 5+ — 페이지네이션, SQL period push, `aggregate.py` 누산 패턴 헬퍼화
