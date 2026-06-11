"""자산 변화 페이지 핵심 알고리즘 — 순수 함수(DB/네트워크 무관).

일별 자산 = Σ_종목 (그 날 보유 수량 × 그 날 종가). 계좌뷰/종목뷰 동일 알고리즘(스코프만 다름).

설계(docs/spec-history/2026-06-04-asset-history-page.md):
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
from invest_note_api.domain.trade_types import (
    Trade,
    currency_for_country,
    to_krw,
    trade_country,
)
from invest_note_api.domain.portfolio import build_positions
from invest_note_api.domain.trade_utils import position_key, to_kst
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


def _gid_for_trade(trade: Trade) -> str:
    """종목 식별 키 = position_key(ticker or asset_name, country)(D2).

    같은 ticker 문자열이라도 country 가 다르면(예: 숫자형 KR 코드 vs US 심볼 충돌) 별도 종목으로
    분리한다. ticker 없는 KR 보유는 asset_name fallback 을 country 와 합성해 보존한다.
    """
    key = trade_to_group_key(trade)
    code = key.ticker or key.asset_name
    return position_key(code, trade_country(trade))


def _qty_steps_by_ticker(
    trades: list[Trade],
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, str]]:
    """종목((ticker|asset_name, country)별 (kst_date, running_qty_after) step 리스트(시간순).

    같은 날 복수 거래면 그 날 마지막 이벤트의 running_qty 만 남긴다(날짜→qty 덮어쓰기).
    그룹키는 `position_key(ticker or asset_name, country)`(D2) — 통화 혼재 스코프에서
    같은 ticker 문자열이 KR/US 로 충돌해도 분리 합산된다.

    Returns:
        (steps, gid_country): gid→step 리스트, gid→country(통화 판정용).
    """
    # gid((ticker|asset_name)+country) → 해당 종목 거래들.
    groups: dict[str, list[Trade]] = {}
    gid_country: dict[str, str] = {}
    for t in trades:
        gid = _gid_for_trade(t)
        groups.setdefault(gid, []).append(t)
        gid_country[gid] = trade_country(t)

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
    return steps, gid_country


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
    usdkrw: float | None = None,
) -> AssetHistoryResult:
    """자산 변화 series/items 산출(통화-aware KRW 합산).

    Args:
        trades: 스코프 거래(계좌뷰=계좌 필터 전체, 종목뷰=단일 종목). KR/US 혼재 가능.
        closes: daily_prices_repo.get_closes 결과에 country 태깅한 행
            [{ticker, close_date, close_price, country}]. country 는 라우터가 country 별
            get_closes 호출 후 merge 전에 각 행에 부여한다(D1) — get_closes 자체는 country 미반환.
        live_quotes: {position_key(ticker, country): 라이브 종가(native)} (오늘 점용).
            누락 종목은 직전 종가로 fallback.
        today: KST 오늘 날짜.
        is_stock_view: 종목뷰면 items 에 close(native)/qty 추가(단일 종목 가정).
        include_today: 오늘 점 포함 여부 — 휴장일(주말/공휴일)이면 False(market_open_today).
        usdkrw: USD→KRW spot 환율(1개, 일자별 historical 아님). US 보유의 KRW 환산에 사용.
            None 이면 US 종목 기여 제외 + incomplete=True(KR 은 항상 환산 성공).

    series/items 의 value/change 는 **KRW**(통화 혼재 합산은 to_krw 로만, 직접 곱 금지 — D3).
    종목뷰 items 의 close 는 **native 통화 유지**(USD 종목뷰는 USD close).

    Returns:
        AssetHistoryResult(series, items, incomplete).
    """
    if not trades:
        return AssetHistoryResult(series=[], items=[], incomplete=False)

    steps, gid_country = _qty_steps_by_ticker(trades)

    # gid(position_key(ticker, country))별 종가 리스트(날짜 오름차순).
    # closes 는 get_closes 가 ticker,close_date 순 정렬 + 라우터가 country 태깅(D1).
    closes_by_ticker: dict[str, list[tuple[date, float]]] = {}
    for c in closes:
        gid = position_key(c["ticker"], c["country"])
        closes_by_ticker.setdefault(gid, []).append(
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

    # 첫 점(=가장 오래된 거래일)의 전일대비 기준값 = 그날 보유분의 매수 원금(cost_basis, KRW).
    # 직전 점이 없어 0 으로 두던 것을 '구매가 대비 그날 종가'(= value - cost)로 표시하기 위함.
    # gid→cost_basis(KRW, 거래시점 환율 박제) 맵을 그날 시점 보유로 구해, 아래 value 산입과
    # 같은 gid 만 누적(통화 미상으로 value 에서 빠진 종목의 cost 도 함께 빠져 정합 유지).
    first_day = days[0] if days else None
    cost_by_gid: dict[str, float] = {}
    if first_day is not None:
        asof_trades = [t for t in trades if _trade_kst_date(t) <= first_day]
        asof_positions, _ = build_positions(asof_trades)
        cost_by_gid = {
            p.key: p.cost_basis for p in asof_positions if p.holding_quantity > 0
        }
    first_baseline = 0.0

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
            # 종목 통화로 KRW 환산(D3) — USD+usdkrw None 이면 to_krw 가 None → 기여 제외.
            currency = currency_for_country(gid_country.get(gid, ""))
            value_krw = to_krw(qty * price, currency, usdkrw)
            if value_krw is None:
                incomplete = True  # USD 인데 환율 미상 → silent KRW 합산 방지(기여 제외).
                if is_stock_view and gid == stock_gid:
                    per_day_close_qty[d] = (price, qty)  # close 는 native 유지(D4 안내용).
                continue
            total += value_krw
            if d == first_day:
                # 매칭 cost 없으면 value_krw 폴백 → 그 gid 의 change 기여 0(기존 동작 보존).
                first_baseline += cost_by_gid.get(gid, value_krw)
            if is_stock_view and gid == stock_gid:
                per_day_close_qty[d] = (price, qty)  # close 는 native 통화 유지.
        series.append({"date": d.isoformat(), "value": total})

    # items: 동일 날짜집합 역순(최신 먼저). change = 직전 거래일 대비 value 차.
    # 첫 항목(i==0)은 직전 점이 없어 매수 원금(first_baseline)을 기준으로 → change = 당일종가 - 구매가.
    items: list[dict] = []
    for i, point in enumerate(series):
        prev_value = series[i - 1]["value"] if i > 0 else first_baseline
        change = point["value"] - prev_value
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
