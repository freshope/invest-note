# Spec: portfolio summary 풀스캔 1회 통합

> 완료: 2026-04-30

## 배경 / 문제

`/api/portfolio/summary` 핫패스에서 동일한 `trades` 리스트를 여러 번 풀스캔한다.

현재 `routers/portfolio.py:98-108` 에서 호출되는 도메인 함수의 trades 순회 비용:

| 함수 | 위치 | trades 순회 |
|------|------|-------------|
| `build_positions(trades)` | `domain/portfolio.py:91` | 분류 1회 + lot별 `walk_trades` (합계 1회) = **2회** |
| `build_account_snapshots(accounts, trades, quotes)` | `domain/portfolio.py:219` | 계좌 분류 1회 + 계좌별 순회 (합계 1회) = **2회** |
| `build_totals(positions, accounts, trades)` | `domain/portfolio.py:263` | 내부 `build_pnl_map` 1회 + month 집계 1회 = **2회** |

총 **6회 풀스캔**. 또한 `build_account_snapshots` 의 `cost_basis` 누적(L241)은 사용되지 않는 dead code.

`build_positions` 가 이미 `lot_map` (계좌·종목별 잔량/원가)을 만들고 있으므로 이를 외부에 노출해 `build_account_snapshots` 에서 재사용하면 trades 풀스캔 2회를 0회로 줄일 수 있다. `build_pnl_map` 도 라우터에서 1회만 빌드해 `build_totals` 에 주입하면 중복 빌드를 제거할 수 있다.

## 목표

- `/api/portfolio/summary` 에서 trades 풀스캔이 **6회 → 4회 이하**로 감소
- `build_account_snapshots` 가 trades 를 직접 받지 않고 `lot_map` 만으로 stock_evaluation 계산
- `build_totals` 가 `build_pnl_map` 을 내부에서 호출하지 않고 외부에서 주입받음
- `build_account_snapshots` 의 미사용 `cost_basis` 누적 제거
- `test_portfolio_logic.py` / `test_portfolio.py` 전부 통과 (`cd api && poetry run pytest tests/test_portfolio_logic.py tests/test_portfolio.py -q`)
- 기존 응답 JSON 스키마/값 동일 (회귀 없음)

## 설계

### 접근 방식

**1. `build_positions` 시그니처 확장**
- 리턴 타입을 `list[Position]` → `tuple[list[Position], LotMap]` 로 변경
- `LotMap = dict[str, dict]` (lot_key → lot dict, 기존 내부 자료구조 그대로 노출)
- `lot` dict 의 핵심 키: `ticker`, `country`, `account_id`, `running_qty`, `running_cost` (snapshot 계산에 필요)

**2. `build_account_snapshots(accounts, lot_map, quotes)` 로 시그니처 변경**
- trades 인자 제거, lot_map 인자 추가
- 내부 로직: `for lot in lot_map.values()` 로 순회하며 `account_id` 별로 그룹화 → `running_qty > 0` 인 lot의 `quote.price * running_qty` 합산
- `cost_basis` 누적 제거 (어차피 stock_evaluation 계산에 사용되지 않음)

**3. `build_totals(positions, accounts, trades, pnl_map)` 로 시그니처 변경**
- `pnl_map` 인자 추가 (내부 `build_pnl_map(trades)` 호출 제거)
- trades 는 month_realized_pnl / month_trade_count 계산에 여전히 필요하므로 유지
- 결과적으로 trades 순회는 month 집계 1회만 남음 (이전 2회 → 1회)

> **시그니처 결정 근거**: backlog 항목은 `build_totals(positions, accounts, pnl_map)` 형태를 제안했으나, `month_trade_count` 는 SELL/BUY 모두 카운트하고 `traded_at` 기준 month 필터링이 필요하므로 trades 가 여전히 필요하다. trades 인자를 유지하되 `pnl_map` 빌드만 외부로 끌어내 중복 호출을 제거하는 게 단순하고 안전하다.

**4. 라우터 변경 (`routers/portfolio.py:85-116`)**
```python
positions0, lot_map = build_positions(trades)
pnl_map = build_pnl_map(trades)
quotes = await fetch_quotes_by_keys([p.key for p in positions0])
positions = merge_quotes(positions0, quotes)
snapshots = build_account_snapshots(accounts, lot_map, quotes)
totals = build_totals(positions, accounts, trades, pnl_map)
```

**5. `analysis.py` 호출처 호환** (`routers/analysis.py:81`)
- `positions0 = build_positions(all_trades)` → `positions0, _ = build_positions(all_trades)` 로 unpacking 처리
- 다른 변경 없음 (`build_account_snapshots` / `build_totals` 는 analysis 라우터에서 호출되지 않음)

### 주요 변경 파일

- `api/src/invest_note_api/domain/portfolio.py` — 3개 함수 시그니처/내부 로직 변경, dead code 제거
- `api/src/invest_note_api/routers/portfolio.py` — summary 라우터에서 lot_map / pnl_map 주입
- `api/src/invest_note_api/routers/analysis.py` — `build_positions` tuple unpacking 1줄 수정
- `api/tests/test_portfolio_logic.py` — `build_positions` (5개 케이스 L73-108), `build_account_snapshots` (3개 L163-182), `build_totals` (2개 L208-234) 호출 시그니처 갱신
- `api/tests/test_portfolio.py` — 통합 테스트는 라우터 응답만 검증하므로 변경 불필요 예상 (확인 후 결정)

### 재사용 함수

- `build_pnl_map(trades)` (`domain/realized_pnl.py:214`) — 그대로 사용, 라우터에서 직접 호출
- `walk_trades` / `merge_quotes` — 변경 없음

## 구현 체크리스트

- [x] `domain/portfolio.py`: `build_positions` 리턴을 `tuple[list[Position], dict[str, dict]]` 로 변경하고 `lot_map` 반환
- [x] `domain/portfolio.py`: `build_account_snapshots` 시그니처를 `(accounts, lot_map, quotes)` 로 변경, lot 기반으로 stock_evaluation 계산, `cost_basis` 누적 제거
- [x] `domain/portfolio.py`: `build_totals` 시그니처를 `(positions, accounts, trades, pnl_map)` 로 변경, 내부 `build_pnl_map` 호출 제거 + import 정리
- [x] `routers/portfolio.py`: `get_portfolio_summary` 에서 `lot_map` / `pnl_map` 주입 흐름으로 수정
- [x] `routers/analysis.py`: `build_positions` 호출부 unpacking 처리
- [x] `tests/test_portfolio_logic.py`: 호출 시그니처 갱신 + 새 시그니처에 맞춘 케이스 추가 (lot_map 반환 검증, build_account_snapshots 가 lot_map 입력 받는 경로)
- [x] 백엔드 테스트 통과 (`cd api && poetry run pytest tests/test_portfolio.py tests/test_portfolio_logic.py tests/test_realized_pnl.py -q`)
- [x] 전체 백엔드 테스트 통과 (`cd api && poetry run pytest -q`) — analysis.py 영향 회귀 확인
- [x] issue-history 보관 + backlog 항목 체크 처리

## 우려사항 / 리스크

- **lot_map 자료구조 노출**: 현재 `dict[str, dict]` 구조라 타입 안전성 낮음. 향후 `Lot` dataclass 화 가능하지만 본 작업 범위 외 (Tier 2 헬퍼 추출 항목과 묶어 처리). 본 작업에서는 dict 그대로 노출하되 라우터/테스트 외부 사용처는 read-only 로 취급.
- **`build_account_snapshots` 결과 동일성**: 기존 로직은 trade.price 기반 cost_basis 누적 후 quote.price 로 평가했고 cost_basis 는 결과에 영향이 없었음. 새 로직(lot.running_qty * quote.price)도 동일 결과여야 함. lot.running_qty 는 `walk_trades` 의 stored_avg_cost_deduction 결과로, BUY 합계 - SELL 합계 = `qty (BUY) - qty (SELL)` 와 일치 (기존 로직과 동치). `running_qty <= 0` 필터 동일하게 적용.
- **테스트 시그니처 변경 범위**: `test_portfolio_logic.py` 의 build_account_snapshots 케이스 3개는 `[buy]` / `[buy]` / `[buy]` 형태 trades 를 넘기는데, 이를 `build_positions([buy])` 가 만든 lot_map 으로 변환해야 함. 새 헬퍼 또는 직접 build_positions 호출로 처리.
- **oversell 케이스 동치성**: 기존 `build_account_snapshots` 의 `p["qty"] = BUY.qty - SELL.qty` 는 음수 가능 (이후 `<= 0` 필터). 새 경로의 `lot.running_qty` 는 `walk_trades` 가 oversell 시 0으로 clamp. `validate_mutation` 통과한 trades 에서는 동치이지만, 테스트 fixture 가 `[buy, sell, sell]` 로 oversell 을 만들면 결과가 다를 수 있음. 테스트 재작성 시 fixture 검토 필수.
- **account_id 문자열 동등성**: `lot["account_id"]` 는 `Trade.account_id` 원본을 그대로 보존. `_account_from_row` 는 `account.id` 를 `str(...)` 로 강제 변환. snapshot 그룹화 시 `str(lot["account_id"]) == account.id` 형태로 비교해야 UUID 객체가 들어와도 매칭됨. 구현 시 lot_map 키 보관 시점에 `str()` 적용을 권장.

## 검증 방법

1. **단위/통합 테스트**:
   - `cd api && poetry run pytest tests/test_portfolio.py tests/test_portfolio_logic.py tests/test_realized_pnl.py -q`
   - 전체: `cd api && poetry run pytest -q`

2. **수동 회귀 (선택)**:
   - 로컬 `/api/portfolio/summary` 응답을 변경 전후로 캡처해 JSON diff 가 없는지 확인
   - `totals.total_realized_pnl` / `totals.month_realized_pnl` / `snapshots[].stock_evaluation` 동일 값 확인

3. **타입 체크**:
   - `cd api && poetry run mypy src/invest_note_api/domain/portfolio.py src/invest_note_api/routers/portfolio.py src/invest_note_api/routers/analysis.py` (프로젝트가 mypy 사용 시)
