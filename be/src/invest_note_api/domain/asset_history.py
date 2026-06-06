"""자산 변화 페이지 핵심 알고리즘 — 순수 함수(DB/네트워크 무관).

일별 자산 = Σ_종목 (그 날 보유 수량 × 그 날 종가). 계좌뷰/종목뷰 동일 알고리즘(스코프만 다름).

설계(spec-current.md):
  1. 스코프 거래를 종목별로 묶어 `sort_for_calc → walk_trades` 로 수량 step function 산출.
     ⚠️ walk_trades 는 단일 그룹 walker라 다종목을 한 번에 walk 하면 수량이 섞인다 → 반드시
        종목(ticker+country)별로 따로 walk 후 날짜별 합산한다(G1: sort_for_calc 필수).
  2. 날짜 범위 = [max(스코프 최초 매수일, 오늘-2년), 오늘].
  3. 거래일 집합 = 적재 종가 close_date 합집합(∪ 오늘 — 단, 개장일일 때만. 휴장일 점 방지).
  4. 각 거래일 d: 자산(d) = Σ_종목 qty(d) × close≤d(종목)  (종목별 직전 종가 carry-forward).
  5. d=오늘: 저장 종가 대신 라이브 시세(인자 주입).
  6. carry-forward 불가(qty>0 인데 그 종목 close≤d 가 없음)면 그 종목 기여 제외 + incomplete=True.

자산 = 보유 종목 평가액(현금 잔고 제외).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from invest_note_api.domain.realized_pnl import sort_for_calc, trade_to_group_key
from invest_note_api.domain.trade_types import Trade
from invest_note_api.domain.trade_utils import to_kst
from invest_note_api.domain.trade_walker import walk_trades

# 최대 2년 윈도우(spec). 오늘 기준 lookback. 종가 사전적재(daily_price_seed)와 공유 —
# 히스토리 계산 창과 적재 창이 어긋나지 않도록 단일 정의를 유지한다.
LOOKBACK_DAYS = 365 * 2


@dataclass(frozen=True)
class AssetHistoryResult:
    """series: 차트 점(날짜 오름차순) / items: 목록(최신 먼저). incomplete: 부분 표시 플래그."""

    series: list[dict]
    items: list[dict]
    incomplete: bool


def _pos_or_none(price: float | None) -> float | None:
    """0/음수 가격은 결측 취급(데이터 오염 가드) — qty×0 이 조용히 합산되지 않고 incomplete 경로로 보낸다."""
    return price if price is not None and price > 0 else None


def _trade_kst_date(trade: Trade) -> date:
    """traded_at(timestamptz) → KST 날짜. close_date(date)와 같은 기준으로 비교(장 마감 근처 오차 방지)."""
    return to_kst(trade.traded_at).date()


def _qty_steps_by_ticker(trades: list[Trade]) -> dict[str, list[tuple[date, float]]]:
    """종목(ticker)별 (kst_date, running_qty_after) step 리스트(시간순).

    같은 날 복수 거래면 그 날 마지막 이벤트의 running_qty 만 남긴다(날짜→qty 덮어쓰기).
    그룹키는 기존 trade_to_group_key(account,ticker,country) 기반이되, 종목 차원만 쓰므로
    ticker(없으면 asset_name)로 묶는다 — 같은 종목을 여러 계좌서 보유해도 합산이 목적.
    """
    # ticker(또는 asset_name) → 해당 종목 거래들.
    groups: dict[str, list[Trade]] = {}
    for t in trades:
        key = trade_to_group_key(t)
        gid = key.ticker or key.asset_name
        groups.setdefault(gid, []).append(t)

    steps: dict[str, list[tuple[date, float]]] = {}
    for gid, group_trades in groups.items():
        # 같은 그룹 안에서 walk_trades 가 sort_for_calc 로 정렬·누적(G1).
        date_to_qty: dict[date, float] = {}
        for ev in walk_trades(
            group_trades,
            group_filter=lambda _t: True,  # 이미 종목 단위로 묶음.
            sort_fn=sort_for_calc,
            track_fifo_lots=False,
        ):
            date_to_qty[_trade_kst_date(ev.trade)] = ev.state_after.running_qty
        steps[gid] = sorted(date_to_qty.items())
    return steps


def _qty_on(steps: list[tuple[date, float]], d: date) -> float:
    """date d 시점 보유 수량 = kst_date ≤ d 인 마지막 step 값(없으면 0)."""
    qty = 0.0
    for step_date, step_qty in steps:
        if step_date <= d:
            qty = step_qty
        else:
            break
    return qty


def _close_on(closes: list[tuple[date, float]], d: date) -> float | None:
    """date d 시점 종가 = close_date ≤ d 인 마지막 값(carry-forward). 없으면 None."""
    price: float | None = None
    for close_date, close_price in closes:
        if close_date <= d:
            price = close_price
        else:
            break
    return price


def _first_buy_date(trades: list[Trade]) -> date | None:
    buys = [_trade_kst_date(t) for t in sort_for_calc(trades) if t.trade_type == "BUY"]
    return min(buys) if buys else None


def market_open_today(quotes: list[dict | None], today: date) -> bool:
    """오늘 개장 여부 — 시세 응답의 마지막 체결 날짜(traded_on)로 판정.

    하나라도 traded_on == today 면 개장(휴장일이면 모든 종목이 직전 거래일을 가리킴).
    traded_on 을 아는 시세가 없으면(전체 실패/소스 미지원) 평일 여부로 fallback —
    이 경로에선 평일 공휴일을 못 거르지만 기존 동작 이상으로 나빠지지 않는다.
    """
    known = [q["traded_on"] for q in quotes if q and q.get("traded_on")]
    if known:
        return today.isoformat() in known
    return today.weekday() < 5


def compute_asset_history(
    trades: list[Trade],
    closes: list[dict],
    live_quotes: dict[str, float],
    *,
    today: date,
    is_stock_view: bool,
    include_today: bool = True,
) -> AssetHistoryResult:
    """자산 변화 series/items 산출.

    Args:
        trades: 스코프 거래(계좌뷰=계좌 필터 전체, 종목뷰=단일 종목).
        closes: daily_prices_repo.get_closes 결과 [{ticker, close_date, close_price}].
        live_quotes: {ticker: 라이브 종가} (오늘 점용). 누락 종목은 직전 종가로 fallback.
        today: KST 오늘 날짜.
        is_stock_view: 종목뷰면 items 에 close/qty 추가(단일 종목 가정).
        include_today: 오늘 점 포함 여부 — 휴장일(주말/공휴일)이면 False(market_open_today).

    Returns:
        AssetHistoryResult(series, items, incomplete).
    """
    if not trades:
        return AssetHistoryResult(series=[], items=[], incomplete=False)

    steps = _qty_steps_by_ticker(trades)

    # ticker(gid)별 종가 리스트(날짜 오름차순). closes 는 get_closes 가 ticker,close_date 순 정렬.
    closes_by_ticker: dict[str, list[tuple[date, float]]] = {}
    for c in closes:
        closes_by_ticker.setdefault(c["ticker"], []).append(
            (c["close_date"], c["close_price"])
        )

    # 날짜 범위: [max(최초 매수일, 오늘-2년), 오늘].
    first_buy = _first_buy_date(trades)
    if first_buy is None:
        return AssetHistoryResult(series=[], items=[], incomplete=False)
    range_start = max(first_buy, today - timedelta(days=LOOKBACK_DAYS))

    # 거래일 집합 = 적재 종가 close_date(범위 내) ∪ 오늘(개장일만 — 휴장일 점 방지).
    trading_days: set[date] = {
        cd for cd, _ in (item for lst in closes_by_ticker.values() for item in lst)
        if range_start <= cd <= today
    }
    if include_today:
        trading_days.add(today)
    days = sorted(d for d in trading_days if range_start <= d <= today)

    incomplete = False
    series: list[dict] = []
    # 종목뷰 items 보조: 단일 종목의 그날 종가/수량.
    stock_gid = next(iter(steps), None) if is_stock_view else None
    per_day_close_qty: dict[date, tuple[float | None, float]] = {}

    for d in days:
        total = 0.0
        for gid, gid_steps in steps.items():
            qty = _qty_on(gid_steps, d)
            if qty <= 0:
                if is_stock_view and gid == stock_gid:
                    per_day_close_qty[d] = (_close_on(closes_by_ticker.get(gid, []), d), 0.0)
                continue
            if d == today:
                price = _pos_or_none(live_quotes.get(gid))
                if price is None:
                    # 라이브 결측 → 직전 종가.
                    price = _pos_or_none(_close_on(closes_by_ticker.get(gid, []), d))
                    incomplete = True
            else:
                price = _pos_or_none(_close_on(closes_by_ticker.get(gid, []), d))
            if price is None:
                incomplete = True  # carry-forward 불가(첫 적재 종가 이전) → 기여 제외.
                if is_stock_view and gid == stock_gid:
                    per_day_close_qty[d] = (None, qty)
                continue
            total += qty * price
            if is_stock_view and gid == stock_gid:
                per_day_close_qty[d] = (price, qty)
        series.append({"date": d.isoformat(), "value": total})

    # items: 동일 날짜집합 역순(최신 먼저). change = 직전 거래일 대비 value 차(첫 항목 0).
    items: list[dict] = []
    for i, point in enumerate(series):
        prev_value = series[i - 1]["value"] if i > 0 else point["value"]
        change = point["value"] - prev_value  # i==0 이면 0.
        item: dict = {
            "date": point["date"],
            "value": point["value"],
            "change": change,
        }
        if is_stock_view:
            d = date.fromisoformat(point["date"])
            close, qty = per_day_close_qty.get(d, (None, 0.0))
            item["close"] = close
            item["qty"] = qty
        items.append(item)
    items.reverse()  # 최신 먼저.

    return AssetHistoryResult(series=series, items=items, incomplete=incomplete)


def scope_earliest_date(trades: list[Trade], today: date) -> date:
    """backfill 시작일 = max(최초 매수일, 오늘-2년). 거래 없으면 today(no-op)."""
    first_buy = _first_buy_date(trades)
    floor = today - timedelta(days=LOOKBACK_DAYS)
    if first_buy is None:
        return today
    return max(first_buy, floor)


def scope_tickers(trades: list[Trade]) -> list[str]:
    """스코프 보유 종목 ticker 목록(중복 제거). asset_name 만 있는 종목은 적재 불가라 제외."""
    seen: list[str] = []
    for t in trades:
        tk = t.ticker_symbol
        if tk and tk not in seen:
            seen.append(tk)
    return seen
