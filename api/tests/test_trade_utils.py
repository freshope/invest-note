"""순수 함수 단위 테스트 — domain/trade_utils.py"""
from datetime import date, datetime, time, timezone

from invest_note_api.domain.trade_utils import KST, kst_date_to_utc, to_kst


def test_kst_date_to_utc_default_market_open():
    result = kst_date_to_utc(date(2026, 4, 29))
    assert result == datetime(2026, 4, 29, 0, 0, tzinfo=timezone.utc)


def test_kst_date_to_utc_custom_time():
    result = kst_date_to_utc(date(2026, 4, 29), time(15, 30))
    assert result == datetime(2026, 4, 29, 6, 30, tzinfo=timezone.utc)


def test_to_kst_naive_datetime_assumed_utc():
    result = to_kst(datetime(2026, 4, 29, 0, 0))
    assert result.tzinfo == KST
    assert result.hour == 9
