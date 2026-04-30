"""domain/trade_import.py 단위 테스트."""

from datetime import date
from decimal import Decimal

import pytest

from invest_note_api.domain.trade_import import (
    ImportSummary,
    make_preview_signature,
    make_signature,
)


def sig(account_id="acct1", trade_date="2026-01-15", ticker="005930",
        asset_name="삼성전자", trade_type="BUY", quantity=10, price=70000):
    return make_signature(
        account_id=account_id,
        trade_date=date.fromisoformat(trade_date),
        ticker=ticker,
        asset_name=asset_name,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
    )


def test_same_inputs_produce_same_signature():
    s1 = sig()
    s2 = sig()
    assert s1 == s2


def test_different_date_different_signature():
    s1 = sig(trade_date="2026-01-15")
    s2 = sig(trade_date="2026-01-16")
    assert s1 != s2


def test_different_trade_type_different_signature():
    s1 = sig(trade_type="BUY")
    s2 = sig(trade_type="SELL")
    assert s1 != s2


def test_different_quantity_different_signature():
    s1 = sig(quantity=10)
    s2 = sig(quantity=11)
    assert s1 != s2


def test_price_normalised_to_two_decimal():
    # 70000.004 → 70000.00, 70000.005 → 70000.01 (ROUND_HALF_UP)
    s1 = sig(price=70000.001)
    s2 = sig(price=70000.004)
    assert s1 == s2  # 둘 다 70000.00으로 정규화

    s3 = sig(price=70000.005)
    assert s1 != s3  # 70000.01 vs 70000.00


def test_ticker_preferred_over_asset_name():
    s_with_ticker = sig(ticker="005930", asset_name="삼성전자")
    s_no_ticker = make_signature(
        account_id="acct1",
        trade_date=date(2026, 1, 15),
        ticker=None,
        asset_name="삼성전자",
        trade_type="BUY",
        quantity=10,
        price=70000,
    )
    # ticker가 있으면 identifier=ticker, 없으면 identifier=asset_name
    assert s_with_ticker != s_no_ticker  # 동일 asset_name이라도 ticker 있으면 identifier 다름


def test_signature_hashable_for_set():
    sigs = {sig(), sig(trade_date="2026-02-01"), sig(trade_type="SELL")}
    assert len(sigs) == 3


def preview_sig(trade_date="2026-01-15", ticker="005930", asset_name="삼성전자",
                trade_type="BUY", quantity=10, price=70000):
    return make_preview_signature(
        trade_date=date.fromisoformat(trade_date),
        ticker=ticker,
        asset_name=asset_name,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
    )


def test_preview_signature_ignores_account_id():
    """PreviewSignature 는 account_id 와 무관하게 동등성을 보장한다."""
    p = preview_sig()
    s_acct1 = sig(account_id="acct1")
    s_acct2 = sig(account_id="acct2")
    # commit signature 두 개는 account_id 만 달라도 다름
    assert s_acct1 != s_acct2
    # preview signature 는 account_id 필드 자체가 없어 동일 입력이면 항상 같음
    p_again = preview_sig()
    assert p == p_again
    # 같은 set 에 두 번 들어가지 않음 → dedup 정확히 동작
    assert len({preview_sig(), preview_sig(trade_date="2026-02-01")}) == 2


def test_import_summary_defaults():
    s = ImportSummary()
    assert s.new_count == 0
    assert s.duplicate_count == 0
    assert s.error_count == 0
    assert s.errors == []
