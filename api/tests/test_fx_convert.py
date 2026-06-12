"""domain.trade_types 통화 환산 헬퍼 — currency_for_country / to_krw."""
from __future__ import annotations

from invest_note_api.domain.trade_types import currency_for_country, to_krw


def test_currency_for_country():
    assert currency_for_country("US") == "USD"
    assert currency_for_country("KR") == "KRW"
    assert currency_for_country("OTHER") == "KRW"


def test_to_krw_krw_passthrough():
    # KRW 는 환율 없이도 그대로
    assert to_krw(70000.0, "KRW", None) == 70000.0
    assert to_krw(70000.0, "KRW", 1500.0) == 70000.0


def test_to_krw_usd_converts():
    assert to_krw(100.0, "USD", 1500.0) == 150000.0


def test_to_krw_usd_without_rate_is_none():
    # 환율을 못 받으면 None → 호출측이 missing 처리(조용한 혼재 합산 방지)
    assert to_krw(100.0, "USD", None) is None


def test_to_krw_unknown_currency_is_none():
    assert to_krw(100.0, "JPY", 1500.0) is None
