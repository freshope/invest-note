# Spec: BE simplify Round 4 — 도메인 정리 (walker 통합 + build_positions 분리)

## 배경 / 문제

`docs/backlog.md` "BE simplify" 섹션 Round 1·2·3 처리 후 9 개 항목이 남아있다. Round 4 는 **"도메인 정리"** 카테고리 2 개 항목을 묶는다 — 동작 변경 없음, 코드 중복 제거 + 가독성 개선.

- **Round 1** (2026-05-01) — `model_copy(update=)` / `dataclasses.replace` / `sort_by_traded_at` 통합
- **Round 2** (2026-05-03) — 응답 매핑 청소 4 개
- **Round 3** (2026-05-03) — 효율/핫패스 4 개 (httpx lifespan, parser threadpool, import date 범위, delete 통합)
- **Round 4** (이번) — 도메인 정리 2 개

1. **`compute_holding_summary` → `walk_trades` 위에 재구성** — 현재 `holdings.py:36` 가 walker 와 동일한 BUY/SELL 누산 로직을 인라인 재구현. walker 의 terminal `state_after` 만 취해 의미 통일.
2. **`build_positions` 119줄 함수 분리** — `domain/portfolio.py:103-221` 의 두 단계 (trades→lot_map / lot_map→positions) 가 한 함수에 합쳐져 가독성/단위 테스트 어려움. `_build_lot_map` + `_lot_to_positions` 로 분리.

이후 라운드 (재사용/잔여 7 개) 는 별도 spec 으로 분리.

## 목표

- `compute_holding_summary` 가 인라인 WAC 누산 7 줄을 제거하고 `walk_trades` 의 terminal state 를 사용한다 — `HoldingSummary(quantity, avg_buy_price)` 반환 시그니처 보존.
- `build_positions` 가 `_build_lot_map(trades) -> LotMap` + `_lot_to_positions(lot_map) -> list[Position]` 두 헬퍼로 분리되고, 공개 함수는 두 헬퍼를 합성한다. 공개 시그니처 `(trades) -> tuple[list[Position], LotMap]` 보존.
- 모든 기존 테스트 (`api/tests/`) 가 그대로 통과한다 — 응답 wire format / 도메인 결과 동일.

## 설계

### 접근 방식

#### 1. `compute_holding_summary` walker 위 재구성

walker 의 default `cost_deduction=recomputed_avg_cost_deduction` 은 `state_before.avg_cost * matched_qty` 로 차감 — 현재 holdings 의 `avg_cost = running_cost / running_qty`, `running_cost - avg_cost * matched` 와 동일. SELL 시 walker 의 `running_qty -= trade.quantity` 와 holdings 의 `running_qty -= matched(=min(qty, rq))` 는 `max(0, ...)` 클램프 덕분에 모든 케이스에서 동일 결과.

리팩터:

```python
from invest_note_api.domain.trade_walker import WalkerState, walk_trades

def compute_holding_summary(trades: list["Trade"], key: TradeGroupKey) -> HoldingSummary:
    """보유 수량과 가중평균단가(WAC)를 한 번의 순회로 계산."""
    final_state = WalkerState(running_qty=0.0, running_cost=0.0)
    for ev in walk_trades(
        trades,
        group_filter=lambda t: is_same_group(t, key),
        sort_fn=sort_by_traded_at,
        track_fifo_lots=False,
    ):
        final_state = ev.state_after

    avg_buy_price = (
        final_state.running_cost / final_state.running_qty
        if final_state.running_qty > 0
        else None
    )
    return HoldingSummary(
        quantity=final_state.running_qty,
        avg_buy_price=avg_buy_price,
    )
```

> walker default 인 `recomputed_avg_cost_deduction` 은 `compute_holding_summary` 의 의도(저장값 무시, 누적된 WAC 사용)와 일치. `track_fifo_lots=False` 로 불필요한 FIFO queue 작업 회피.

import 정리:
- 추가: `WalkerState`, `walk_trades` (`domain.trade_walker`)
- 제거: `TRADE_TYPE_BUY` (이제 미사용)

#### 2. `build_positions` 분리

현재 함수의 두 단계가 명확:
- **Phase 1** (lines 110-162): `trades_by_lot` → 각 lot 의 walker 누산 → `lot_map`
- **Phase 2** (lines 164-219): `lot_map` 의 보유수량 > 0 lot 을 display_key 별로 그룹/집계 → `positions`

두 헬퍼로 추출하고 `build_positions` 는 합성만 담당:

```python
def _build_lot_map(trades: list["Trade"]) -> LotMap:
    """trades → lot_map: 계좌별 종목 lot 의 walker 누산."""
    trades_by_lot: dict[str, list["Trade"]] = defaultdict(list)
    for trade in trades:
        trades_by_lot[_lot_key_of(trade)].append(trade)

    lot_map: LotMap = {}
    for lot_key, lot_trades in trades_by_lot.items():
        first = lot_trades[0]
        exchange = ""
        running_qty = 0.0
        running_cost = 0.0
        realized_pnl = 0.0
        last_traded_at = first.traded_at.isoformat()
        last_note_type: str | None = None
        last_note: str | None = None

        for ev in walk_trades(
            lot_trades,
            group_filter=lambda _t: True,
            sort_fn=sort_by_traded_at,
            cost_deduction=stored_avg_cost_deduction,
            track_fifo_lots=False,
        ):
            last_traded_at = ev.trade.traded_at.isoformat()
            if ev.trade.exchange:
                exchange = ev.trade.exchange
            if ev.kind == "BUY":
                reason = (ev.trade.buy_reason or "").strip()
                if reason:
                    last_note_type = NOTE_TYPE_REASON
                    last_note = reason
            else:
                realized_pnl += ev.trade.profit_loss or 0.0
                note = (ev.trade.sell_reason or "").strip()
                if note:
                    last_note_type = NOTE_TYPE_SELL
                    last_note = note
            running_qty = ev.state_after.running_qty
            running_cost = ev.state_after.running_cost

        lot_map[lot_key] = Lot(
            ticker=trade_identifier(first),
            country=trade_country(first),
            asset_name=first.asset_name,
            account_id=str(first.account_id),
            exchange=exchange,
            running_qty=running_qty,
            running_cost=running_cost,
            realized_pnl=realized_pnl,
            last_traded_at=last_traded_at,
            last_note_type=last_note_type,
            last_note=last_note,
        )
    return lot_map


def _lot_to_positions(lot_map: LotMap) -> list[Position]:
    """lot_map → positions: 보유수량 > 0 lot 을 종목별(`TICKER:COUNTRY`) 로 집계."""
    pos_map: dict[str, dict] = {}
    for lot in lot_map.values():
        if lot.running_qty <= 0:
            continue
        display_key = position_key(lot.ticker, lot.country)
        if display_key not in pos_map:
            pos_map[display_key] = {
                "ticker": lot.ticker,
                "country": lot.country,
                "asset_name": lot.asset_name,
                "exchange": lot.exchange,
                "running_qty": 0.0,
                "running_cost": 0.0,
                "realized_pnl": 0.0,
                "last_traded_at": lot.last_traded_at,
                "account_ids": set(),
                "last_note_type": None,
                "last_note": None,
            }
        pos = pos_map[display_key]
        pos["running_qty"] += lot.running_qty
        pos["running_cost"] += lot.running_cost
        pos["realized_pnl"] += lot.realized_pnl
        if lot.last_traded_at > pos["last_traded_at"]:
            pos["last_traded_at"] = lot.last_traded_at
        if lot.exchange:
            pos["exchange"] = lot.exchange
        pos["account_ids"].add(lot.account_id)
        if lot.last_note_type:
            pos["last_note_type"] = lot.last_note_type
            pos["last_note"] = lot.last_note

    positions: list[Position] = []
    for key, pos in pos_map.items():
        holding_qty = pos["running_qty"]
        avg_buy_price = pos["running_cost"] / holding_qty if holding_qty > 0 else 0.0
        positions.append(Position(
            key=key,
            ticker=pos["ticker"],
            country=pos["country"],
            asset_name=pos["asset_name"],
            exchange=pos["exchange"],
            holding_quantity=holding_qty,
            avg_buy_price=avg_buy_price,
            cost_basis=pos["running_cost"],
            realized_pnl=pos["realized_pnl"],
            current_price=None,
            evaluation=None,
            unrealized_pnl=None,
            last_note_type=pos["last_note_type"],
            last_note=pos["last_note"],
            last_traded_at=pos["last_traded_at"],
            account_ids=list(pos["account_ids"]),
        ))
    return positions


def build_positions(trades: list["Trade"]) -> tuple[list[Position], LotMap]:
    """계좌별 lot 추적 → 종목별 포지션 집계.

    Returns:
        (positions, lot_map): 보유 수량 > 0인 포지션 리스트와 lot_key → Lot.
        `lot_map` 은 `build_account_snapshots` 등 후속 단계에서 재사용된다.
    """
    lot_map = _build_lot_map(trades)
    positions = _lot_to_positions(lot_map)
    return positions, lot_map
```

> 두 헬퍼는 각각 ~50 줄로 단위 테스트 / 가독성 향상. 공개 `build_positions` 는 5 줄로 단순화. 호출자 (`routers/portfolio.py:87`, `routers/analysis.py`) 와 테스트 (`test_portfolio_logic.py`) 는 무영향.

### 주요 변경 파일

- `api/src/invest_note_api/domain/holdings.py` — `compute_holding_summary` 를 walker 기반으로 재구성, `TRADE_TYPE_BUY` import 제거, `WalkerState`/`walk_trades` import 추가
- `api/src/invest_note_api/domain/portfolio.py` — `build_positions` 119 줄을 `_build_lot_map` + `_lot_to_positions` + 합성 5 줄로 분리

### 재사용할 기존 유틸

- `domain/trade_walker.walk_trades`, `WalkerState`, `stored_avg_cost_deduction` (이미 `portfolio.py` 사용 중)
- `domain/trade_utils.sort_by_traded_at` (Round 1 에서 통합된 헬퍼)
- `domain/realized_pnl.is_same_group`, `TradeGroupKey` (`holdings.py` 기존 import)

## 구현 체크리스트

- [ ] `domain/holdings.py` — import 정리 (`TRADE_TYPE_BUY` 제거, `WalkerState`/`walk_trades` 추가)
- [ ] `domain/holdings.py:36` — `compute_holding_summary` 본문을 walker terminal state 기반으로 재구성
- [ ] `domain/portfolio.py` — `_build_lot_map(trades) -> LotMap` 헬퍼 추출 (lines 110-162 의 Phase 1)
- [ ] `domain/portfolio.py` — `_lot_to_positions(lot_map) -> list[Position]` 헬퍼 추출 (lines 164-219 의 Phase 2)
- [ ] `domain/portfolio.py` — `build_positions` 본문을 두 헬퍼 합성 (5 줄) 로 단순화, docstring 보존
- [ ] 테스트 통과: `cd api && poetry run pytest -q`

## 우려사항 / 리스크

- **`compute_holding_summary` 의미 보존** — walker default `recomputed_avg_cost_deduction` 사용 시 holdings 의 인라인 로직과 모든 케이스에서 동일 결과 검증 (oversell/no-holding 케이스 `max(0, ...)` 클램프로 합치).
- **`compute_holding_summary` 빈 trades** — 모든 trades 가 `is_same_group` 필터 후 빈 리스트면 walker 가 이벤트를 yield 하지 않음 → `final_state` 가 초기값 `WalkerState(0,0)` 유지 → `avg_buy_price=None`, `quantity=0.0` 반환. 기존 동작과 동일.
- **walker 와 holdings 의 SELL 미세 차이 (`running_qty -= trade.quantity` vs `-= matched`)** — `max(0, ...)` 클램프 덕분에 결과 동일. 단, oversell 케이스에서 `running_cost` 계산 경로 동일성 (둘 다 `state_before.avg_cost * matched_qty` 차감) 확인 완료.
- **`build_positions` 분리는 순수 재배치** — 함수 본문은 그대로 두 헬퍼로 옮기고 공개 함수에서 합성. 입출력 시그니처 무변, 내부 `_lot_key_of` 헬퍼는 `_build_lot_map` 안에서만 사용 → 위치 그대로 유지.
- **TestBuildPositions / TestComputeHoldingSummary** — 두 함수의 입출력 검증이라 분리/리팩터 후에도 그대로 통과해야 함. 차이가 발생하면 의미 보존 위반 → 즉시 롤백.

## 검증 방법

```bash
cd api && poetry run pytest -q
```

핵심 테스트 그룹:
- `tests/test_holdings.py` — `TestComputeHoldingSummary` (BUY 단순, partial SELL, multi-BUY+SELL 케이스 — WAC 동일성)
- `tests/test_portfolio_logic.py` — `TestBuildPositions` (single buy / full sell / multi-account / note tracking / realized_pnl), `TestBuildAccountSnapshots` (lot_map 재사용)
- `tests/test_trade_walker.py` — walker 자체 회귀 (compute_holding_summary 가 의존하는 default cost_deduction 동작)
- `tests/test_realized_pnl.py` — `compute_group_pnl` / `validate_mutation` 회귀 (분리된 portfolio 가 영향 주지 않음 검증)
- `tests/test_pnl_sync.py` — 통합 회귀

mypy/타입 체크는 백엔드 별도 설정 없으므로 pytest 통과로 갈음.

## 후속 라운드 (이번 spec 범위 밖)

- **Round 5 — 재사용 / 잔여** (7 개 후보)
  - `accounts_repo.list_accounts` 헬퍼 추출 (라우터 3 곳 인라인 SQL 흡수)
  - `make_signature` ↔ `make_preview_signature` 4 함수 통합 (`account_id: str | None` 단일화 + KST 일자 파싱 헬퍼)
  - `_holding_bucket` / `_size_bucket` 통합 + `Counter`
  - `_decimal_to_float*` 3 validator 공통 헬퍼 (cosmetic)
  - `EMOTION_UNTAGGED` / `TAG_UNTAGGED` Literal 타입 정의
  - `SellBreakdown.is_manual_input` 필드 폐기/명세화 (BE+FE 동기 변경)
  - `_parse_realtime_price` / `_parse_basic_price` 통합 (cosmetic)
- **`GET /api/trades` 페이지네이션** — backlog "효율/핫패스" 잔여 1 개. FE 협조 필요해 BE+FE 동시 spec 으로 별도 분리.
