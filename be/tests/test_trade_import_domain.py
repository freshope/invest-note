"""domain/trade_import.py 단위 테스트."""

from datetime import date, datetime, timezone


from invest_note_api.domain.trade_import import (
    ImportSummary,
    build_merge_patch,
    make_preview_signature,
    make_signature,
)
from invest_note_api.domain.trade_types import Trade


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


# ── build_merge_patch ──────────────────────────────────────────────────────


def _trade(
    *,
    commission: float = 100.0,
    tax: float = 50.0,
    traded_at: datetime = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
) -> Trade:
    """build_merge_patch 테스트용 minimal Trade."""
    return Trade(
        id="trade-1",
        user_id="user-1",
        account_id="acct-1",
        asset_name="삼성전자",
        ticker_symbol="005930",
        market_type="STOCK",
        trade_type="BUY",
        price=70000.0,
        quantity=10.0,
        total_amount=700000.0,
        traded_at=traded_at,
        commission=commission,
        tax=tax,
        created_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
    )


def _row(*, commission: float = 100.0, tax: float = 50.0, traded_at_utc=None) -> dict:
    row = {"commission": commission, "tax": tax}
    if traded_at_utc is not None:
        row["traded_at_utc"] = traded_at_utc
    return row


def test_merge_patch_empty_when_identical():
    existing = _trade(commission=100.0, tax=50.0)
    row = _row(commission=100.0, tax=50.0)
    assert build_merge_patch(existing, row) == {}


def test_merge_patch_detects_commission_change():
    existing = _trade(commission=100.0, tax=50.0)
    row = _row(commission=150.0, tax=50.0)
    assert build_merge_patch(existing, row) == {"commission": 150.0}


def test_merge_patch_detects_tax_change():
    existing = _trade(commission=100.0, tax=50.0)
    row = _row(commission=100.0, tax=75.0)
    assert build_merge_patch(existing, row) == {"tax": 75.0}


def test_merge_patch_detects_both_commission_and_tax():
    existing = _trade(commission=100.0, tax=50.0)
    row = _row(commission=150.0, tax=75.0)
    assert build_merge_patch(existing, row) == {"commission": 150.0, "tax": 75.0}


def test_merge_patch_ignores_traded_at_when_row_has_no_time_info():
    existing = _trade(traded_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc))
    row = _row()  # traded_at_utc 없음
    assert build_merge_patch(existing, row) == {}


def test_merge_patch_detects_traded_at_change_when_row_has_time():
    existing = _trade(traded_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc))
    new_at = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
    row = _row(traded_at_utc=new_at)
    assert build_merge_patch(existing, row) == {"traded_at": new_at}


def test_merge_patch_traded_at_same_no_change():
    same = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    existing = _trade(traded_at=same)
    row = _row(traded_at_utc=same)
    assert build_merge_patch(existing, row) == {}


def test_merge_patch_money_quantized_to_two_decimal():
    # commission 100.001 ↔ 100.004 둘 다 100.00 으로 quantize → 변화 없음
    existing = _trade(commission=100.001, tax=50.0)
    row = _row(commission=100.004, tax=50.0)
    assert build_merge_patch(existing, row) == {}

    # 100.001 ↔ 100.006 은 100.00 vs 100.01 로 다름 (ROUND_HALF_UP)
    row2 = _row(commission=100.006, tax=50.0)
    assert build_merge_patch(existing, row2) == {"commission": 100.01}
