"""순수 함수 단위 테스트 — domain/asset_history.py

합성 거래 + 종가맵으로 일별 자산·carry-forward·오늘 라이브점·change 계산 검증(DB 불필요).
회귀 가드(advisor #1): 2종목·서로 다른 매수/매도일을 종목별 walk 합산으로 산출.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from invest_note_api.domain.asset_history import (
    compute_asset_history,
    market_open_today,
    scope_earliest_date,
    scope_tickers,
)
from invest_note_api.domain.trade_types import Trade


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def make_trade(**kwargs) -> Trade:
    defaults = dict(
        id="t1",
        user_id="u1",
        account_id="a1",
        asset_name="삼성전자",
        ticker_symbol="005930",
        market_type="STOCK",
        trade_type="BUY",
        price=70000.0,
        quantity=10.0,
        total_amount=700000.0,
        traded_at=_dt("2024-01-10T09:00:00+09:00"),
        country_code="KR",
        exchange="",
        commission=0.0,
        tax=0.0,
        created_at=_dt("2024-01-01T00:00:00Z"),
        updated_at=_dt("2024-01-01T00:00:00Z"),
    )
    defaults.update(kwargs)
    return Trade(**defaults)


def _close(ticker: str, d: str, price: float, country: str = "KR") -> dict:
    return {
        "ticker": ticker,
        "close_date": date.fromisoformat(d),
        "close_price": price,
        "country": country,
    }


# ─────────────────────────── 종목뷰(단일 종목) ───────────────────────────


def test_single_stock_qty_times_close():
    """1종목 매수 후 일별 자산 = qty × 그 날 종가, change·close·qty 포함(종목뷰)."""
    trades = [
        make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-02", 75000),
        _close("005930", "2025-06-03", 76000),
    ]
    today = date(2025, 6, 3)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 77000.0}, today=today, is_stock_view=True
    )

    # series: 2개 거래일(6/2 종가, 6/3=오늘 라이브).
    assert res.series == [
        {"date": "2025-06-02", "value": 10 * 75000},
        {"date": "2025-06-03", "value": 10 * 77000},  # 오늘 라이브.
    ]
    # items: 최신 먼저, change = 전 거래일 대비.
    assert res.items[0]["date"] == "2025-06-03"
    assert res.items[0]["change"] == 10 * 77000 - 10 * 75000
    assert res.items[0]["close"] == 77000.0
    assert res.items[0]["qty"] == 10.0
    # 첫 항목(=가장 오래된, 매수일) change = 당일 종가 - 구매가 = (75000-70000)×10.
    assert res.items[1]["change"] == (75000 - 70000) * 10
    assert res.incomplete is False


def test_carry_forward_missing_close():
    """종가 결측일은 직전 종가 carry-forward. 거래일 집합에 없으면 점 자체가 없음."""
    trades = [make_trade(id="b1", quantity=5, traded_at=_dt("2025-06-02T09:00:00+09:00"))]
    closes = [
        _close("005930", "2025-06-02", 100.0),
        # 6/3 결측 → 거래일 집합에 6/3 없음(오늘 6/4 만 추가).
        _close("005930", "2025-06-04", 120.0),
    ]
    today = date(2025, 6, 4)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 130.0}, today=today, is_stock_view=True
    )
    dates = [p["date"] for p in res.series]
    assert dates == ["2025-06-02", "2025-06-04"]
    assert res.series[-1]["value"] == 5 * 130.0  # 오늘 라이브.


def test_incomplete_when_close_before_first():
    """qty>0 인데 그 날 carry-forward 할 종가가 없으면(첫 적재 이전) incomplete=True."""
    trades = [make_trade(id="b1", quantity=5, traded_at=_dt("2025-06-01T09:00:00+09:00"))]
    # 매수는 6/1 이지만 종가는 6/2 부터만 적재됨 → 6/2 거래일에는 종가 있음.
    # 라이브 결측 케이스로 incomplete 유도.
    closes = [_close("005930", "2025-06-02", 100.0)]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={}, today=today, is_stock_view=True
    )
    # 오늘(6/2) 라이브 없음 → 직전 종가 100 fallback + incomplete.
    assert res.series[-1]["value"] == 5 * 100.0
    assert res.incomplete is True


def test_zero_price_treated_as_missing():
    """0/음수 가격(데이터 오염)은 결측 취급 — qty×0 조용한 합산 대신 incomplete=True."""
    trades = [make_trade(id="b1", quantity=5, traded_at=_dt("2025-06-02T09:00:00+09:00"))]
    closes = [
        _close("005930", "2025-06-02", 100.0),
        _close("005930", "2025-06-03", 0.0),  # 오염된 0 종가.
    ]
    today = date(2025, 6, 4)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 0.0}, today=today, is_stock_view=True
    )
    # 6/3: 0 종가 → 결측 취급(기여 제외). 오늘: 0 라이브 → fallback 도 0(6/3 carry) → 결측.
    by_date = {p["date"]: p["value"] for p in res.series}
    assert by_date["2025-06-02"] == 5 * 100.0
    assert by_date["2025-06-03"] == 0.0  # 기여 제외(0 합산이 아니라 스코프 비어 total 0).
    assert res.incomplete is True


# ─────────────────────────── 계좌뷰(다종목) — 회귀 가드 ───────────────────────────


def test_account_view_two_tickers_summed_per_ticker():
    """2종목을 종목별 walk 후 날짜별 합산(단일 walk 면 qty 가 섞여 틀림 — advisor #1 가드)."""
    trades = [
        make_trade(id="a1b", ticker_symbol="005930", asset_name="삼성전자",
                   quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00")),
        make_trade(id="a2b", ticker_symbol="000660", asset_name="하이닉스",
                   quantity=3, traded_at=_dt("2025-06-03T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-02", 70000),
        _close("005930", "2025-06-03", 71000),
        _close("000660", "2025-06-03", 200000),
    ]
    today = date(2025, 6, 3)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 72000.0, "000660:KR": 210000.0},
        today=today, is_stock_view=False,
    )
    by_date = {p["date"]: p["value"] for p in res.series}
    # 6/2: 삼성전자만 보유(10주) — 하이닉스 매수는 6/3.
    assert by_date["2025-06-02"] == 10 * 70000
    # 6/3(오늘 라이브): 삼성 10×72000 + 하이닉스 3×210000.
    assert by_date["2025-06-03"] == 10 * 72000 + 3 * 210000
    # 계좌뷰 items 에는 close/qty 없음.
    assert "close" not in res.items[0]
    assert "qty" not in res.items[0]


def test_first_day_change_is_value_minus_cost_basis():
    """첫 거래일 change = 그날 자산 - 그날 보유분 매수 원금(0 대신 '구매가 대비 종가').

    계좌뷰 합산도 동일 — 첫날 보유 종목들의 cost_basis 합을 기준으로 한다.
    """
    trades = [
        make_trade(id="kb", ticker_symbol="005930", asset_name="삼성전자",
                   quantity=10, price=70000.0, traded_at=_dt("2025-06-02T09:00:00+09:00")),
        make_trade(id="hb", ticker_symbol="000660", asset_name="하이닉스",
                   quantity=2, price=180000.0, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-02", 75000),
        _close("000660", "2025-06-02", 190000),
    ]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 75000.0, "000660:KR": 190000.0},
        today=today, is_stock_view=False,
    )
    # 첫(유일) 거래일 = 매수일. change = (75000-70000)×10 + (190000-180000)×2.
    expected = (75000 - 70000) * 10 + (190000 - 180000) * 2
    assert res.items[0]["change"] == expected


def test_past_day_missing_close_excluded_and_incomplete():
    """과거일에 qty>0 인데 그 종목 close≤d 가 없으면(첫 적재 이전) 그 종목 기여 제외 + incomplete.

    A·B 둘 다 06-01 매수. A 종가는 06-01 부터, B 종가는 06-03 부터 적재 →
    06-01 거래일(A 종가로 집합에 존재)에 B 는 carry-forward 할 종가가 없다.
    """
    trades = [
        make_trade(id="ab", ticker_symbol="005930", asset_name="A",
                   quantity=10, traded_at=_dt("2025-06-01T09:00:00+09:00")),
        make_trade(id="bb", ticker_symbol="000660", asset_name="B",
                   quantity=2, traded_at=_dt("2025-06-01T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-01", 100.0),
        _close("005930", "2025-06-03", 110.0),
        _close("000660", "2025-06-03", 500.0),  # B 는 06-03 부터만.
    ]
    today = date(2025, 6, 3)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 110.0, "000660:KR": 500.0},
        today=today, is_stock_view=False,
    )
    by_date = {p["date"]: p["value"] for p in res.series}
    # 06-01: A 만 평가(10×100). B 는 close≤d 없어 제외.
    assert by_date["2025-06-01"] == 10 * 100.0
    assert res.incomplete is True


def test_sell_reduces_qty():
    """매도 후 보유수량 감소가 자산에 반영(step function)."""
    trades = [
        make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00")),
        make_trade(id="s1", trade_type="SELL", quantity=4, traded_at=_dt("2025-06-03T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-02", 100.0),
        _close("005930", "2025-06-03", 100.0),
    ]
    today = date(2025, 6, 4)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 100.0}, today=today, is_stock_view=True
    )
    by_date = {p["date"]: p["value"] for p in res.series}
    assert by_date["2025-06-02"] == 10 * 100.0
    assert by_date["2025-06-03"] == 6 * 100.0  # 4주 매도 후 6주.


def test_empty_trades():
    res = compute_asset_history([], [], {}, today=date(2025, 6, 4), is_stock_view=False)
    assert res.series == []
    assert res.items == []
    assert res.incomplete is False


# ─────────────────────────── 통화-aware KRW 환산 ───────────────────────────


def test_kr_only_no_usdkrw_unchanged():
    """KR-only 스코프는 usdkrw 없이도(KRW=KRW) 종전과 동일 합산(회귀 가드)."""
    trades = [make_trade(id="b1", quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00"))]
    closes = [_close("005930", "2025-06-02", 75000)]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 77000.0}, today=today,
        is_stock_view=False, usdkrw=None,
    )
    assert res.series[-1]["value"] == 10 * 77000
    assert res.incomplete is False


def test_us_only_krw_converted_with_usdkrw():
    """US-only 종목뷰: value 는 native USD × usdkrw 로 KRW, close 는 native USD 유지."""
    trades = [
        make_trade(id="ub", ticker_symbol="AAPL", asset_name="Apple", country_code="US",
                   quantity=2, price=150.0, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [_close("AAPL", "2025-06-02", 200.0, country="US")]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={"AAPL:US": 210.0}, today=today,
        is_stock_view=True, usdkrw=1300.0,
    )
    # value = 2 × 210(USD) × 1300 = KRW.
    assert res.series[-1]["value"] == 2 * 210.0 * 1300.0
    # close 는 native USD 유지(환산 안 함).
    assert res.items[0]["close"] == 210.0
    assert res.items[0]["qty"] == 2.0
    assert res.incomplete is False


def test_mixed_kr_us_summed_in_krw():
    """KR+US 혼재: 일자별 KRW 합산 = KR native + US native×usdkrw."""
    trades = [
        make_trade(id="kb", ticker_symbol="005930", asset_name="삼성", country_code="KR",
                   quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00")),
        make_trade(id="ub", ticker_symbol="AAPL", asset_name="Apple", country_code="US",
                   quantity=2, price=150.0, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-02", 70000, country="KR"),
        _close("AAPL", "2025-06-02", 200.0, country="US"),
    ]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 72000.0, "AAPL:US": 210.0},
        today=today, is_stock_view=False, usdkrw=1300.0,
    )
    # KRW: 삼성 10×72000 + Apple 2×210×1300.
    assert res.series[-1]["value"] == 10 * 72000 + 2 * 210.0 * 1300.0
    assert res.incomplete is False


def test_us_excluded_when_usdkrw_none_incomplete():
    """usdkrw=None + US 보유: US 기여 제외(to_krw None) + incomplete=True. KR 만 합산."""
    trades = [
        make_trade(id="kb", ticker_symbol="005930", asset_name="삼성", country_code="KR",
                   quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00")),
        make_trade(id="ub", ticker_symbol="AAPL", asset_name="Apple", country_code="US",
                   quantity=2, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-02", 70000, country="KR"),
        _close("AAPL", "2025-06-02", 200.0, country="US"),
    ]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 72000.0, "AAPL:US": 210.0},
        today=today, is_stock_view=False, usdkrw=None,
    )
    # US 제외 → KR 만(10×72000). incomplete=True.
    assert res.series[-1]["value"] == 10 * 72000
    assert res.incomplete is True


def test_us_only_stock_view_usdkrw_none_flat_zero():
    """D4: US-only 종목뷰 + usdkrw=None → series value 전부 0 + incomplete(FE 가 has_foreign 으로 안내).

    BE 가 0 일직선을 내는 것 자체는 정상(US 기여 제외) — FE 가 (has_foreign && usdkrw==null) 로
    0 차트 대신 '환율 불가' 안내를 띄우는 계약. 그 조합을 BE 가 실제로 내는지 가드.
    """
    trades = [
        make_trade(id="ub", ticker_symbol="AAPL", asset_name="Apple", country_code="US",
                   quantity=2, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [_close("AAPL", "2025-06-02", 200.0, country="US")]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={"AAPL:US": 210.0}, today=today,
        is_stock_view=True, usdkrw=None,
    )
    assert all(p["value"] == 0.0 for p in res.series)
    assert res.incomplete is True
    # close 는 native USD 유지(FE 안내 시 가격 표시용).
    assert res.items[0]["close"] == 210.0


def test_same_ticker_different_country_separated():
    """같은 ticker 문자열이 KR/US 동시 보유면 (ticker,country) 키로 분리 합산(키 충돌 가드).

    가상의 ticker 'X' 가 KR(종가 100 KRW)·US(종가 5 USD) 양쪽에 존재 — 키가 ticker 만이면
    종가/수량이 섞이지만, position_key(ticker,country)로 분리되어 각각 환산된다.
    """
    trades = [
        make_trade(id="kx", ticker_symbol="X", asset_name="X-KR", country_code="KR",
                   quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00")),
        make_trade(id="ux", ticker_symbol="X", asset_name="X-US", country_code="US",
                   quantity=4, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [
        _close("X", "2025-06-02", 100.0, country="KR"),
        _close("X", "2025-06-02", 5.0, country="US"),
    ]
    today = date(2025, 6, 2)
    res = compute_asset_history(
        trades, closes, live_quotes={"X:KR": 100.0, "X:US": 5.0},
        today=today, is_stock_view=False, usdkrw=1300.0,
    )
    # KR: 10×100 KRW + US: 4×5×1300 KRW — 섞이지 않고 각 통화로 분리 환산.
    assert res.series[-1]["value"] == 10 * 100.0 + 4 * 5.0 * 1300.0
    assert res.incomplete is False


# ─────────────────────────── 휴장일(오늘 점 제외) ───────────────────────────


def test_holiday_excludes_today_point():
    """휴장일(include_today=False) → 오늘 점 없음, 마지막 점은 직전 거래일(차트가 비지 않음)."""
    trades = [
        make_trade(id="b1", trade_type="BUY", quantity=10, traded_at=_dt("2025-06-02T09:00:00+09:00")),
    ]
    closes = [
        _close("005930", "2025-06-02", 75000),
        _close("005930", "2025-06-03", 76000),
    ]
    today = date(2025, 6, 7)  # 토요일(휴장).
    res = compute_asset_history(
        trades, closes, live_quotes={"005930:KR": 77000.0},
        today=today, is_stock_view=True, include_today=False,
    )

    dates = [p["date"] for p in res.series]
    assert "2025-06-07" not in dates
    assert dates[-1] == "2025-06-03"  # 직전 거래일 점 유지.
    assert res.series[-1]["value"] == 10 * 76000  # 라이브 시세가 아닌 적재 종가.
    assert res.incomplete is False


def test_market_open_today_by_traded_on():
    """traded_on == 오늘인 시세가 하나라도 있으면 개장, 모두 직전 거래일이면 휴장."""
    def q(d):
        return {"price": 1.0, "currency": "KRW", "as_of": "", "traded_on": d}
    # 개장일: 체결 날짜 == 오늘.
    assert market_open_today([q("2026-06-05")], date(2026, 6, 5)) is True
    # 주말: 마지막 체결이 금요일.
    assert market_open_today([q("2026-06-05")], date(2026, 6, 6)) is False
    # 평일 공휴일(핵심): 수요일이지만 체결은 화요일 — weekday 휴리스틱으론 못 거름.
    assert market_open_today([q("2026-09-29")], date(2026, 9, 30)) is False
    # 거래정지 종목 섞임: 하나라도 오늘 체결이면 개장.
    assert market_open_today([q("2026-06-01"), q("2026-06-05")], date(2026, 6, 5)) is True


def test_market_open_today_fallback_weekday():
    """traded_on 을 아는 시세가 없으면(전체 실패/None) 평일 여부 fallback."""
    no_date = {"price": 1.0, "currency": "KRW", "as_of": "", "traded_on": None}
    assert market_open_today([], date(2026, 6, 4)) is True  # 목요일.
    assert market_open_today([], date(2026, 6, 6)) is False  # 토요일.
    assert market_open_today([no_date, None], date(2026, 6, 7)) is False  # 일요일.
    assert market_open_today([no_date], date(2026, 6, 5)) is True  # 금요일.


# ─────────────────────────── scope helpers ───────────────────────────


def test_scope_earliest_clamped_to_two_years():
    trades = [make_trade(traded_at=_dt("2020-01-01T09:00:00+09:00"))]
    today = date(2025, 6, 4)
    earliest = scope_earliest_date(trades, today)
    assert earliest == date(2023, 6, 5)  # 오늘-2년(윤년 포함 730일).


def test_scope_tickers_dedup():
    trades = [
        make_trade(id="t1", ticker_symbol="005930"),
        make_trade(id="t2", ticker_symbol="005930"),
        make_trade(id="t3", ticker_symbol="000660"),
    ]
    assert scope_tickers(trades) == ["005930", "000660"]
