"""ticker_resolver + naver_search 단위 테스트."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from invest_note_api.broker_import.ticker_resolver import resolve_tickers
from invest_note_api.external import naver_search


@pytest.mark.asyncio
async def test_ticker_hint_takes_priority_over_naver():
    """ticker_hints 에 코드가 있으면 Naver 호출 없이 그대로 사용."""
    async def boom(_q, **_kw):
        raise AssertionError("Naver 호출 발생")

    with patch("invest_note_api.broker_import.ticker_resolver.find_first_kr_match", boom):
        result = await resolve_tickers(
            asset_names={"삼성전자"},
            ticker_hints={"삼성전자": "005930"},
        )

    assert result == {"삼성전자": "005930"}


@pytest.mark.asyncio
async def test_naver_match_short_alias():
    """약칭 '현대차' → Naver 1순위 '현대자동차' 매칭."""
    async def fake_match(_q, **_kw):
        return {"code": "FAKE_HMC", "name": "현대자동차", "market": "KR", "exchange": "KOSPI"}

    with patch("invest_note_api.broker_import.ticker_resolver.find_first_kr_match", fake_match):
        result = await resolve_tickers(
            asset_names={"현대차"},
            ticker_hints={},
        )

    assert result == {"현대차": "FAKE_HMC"}


@pytest.mark.asyncio
async def test_naver_match_etf_full_name():
    """ETF 정확명 'TIGER 미국S&P500' → mock 코드 매핑 검증."""
    async def fake_match(_q, **_kw):
        return {"code": "FAKE_TIGER", "name": "TIGER 미국S&P500", "market": "KR", "exchange": "ETF"}

    with patch("invest_note_api.broker_import.ticker_resolver.find_first_kr_match", fake_match):
        result = await resolve_tickers(
            asset_names={"TIGER 미국S&P500"},
            ticker_hints={},
        )

    assert result == {"TIGER 미국S&P500": "FAKE_TIGER"}


@pytest.mark.asyncio
async def test_naver_no_match_returns_none():
    """Naver 결과 없으면 미해결 (None)."""
    async def fake_match(_q, **_kw):
        return None

    with patch("invest_note_api.broker_import.ticker_resolver.find_first_kr_match", fake_match):
        result = await resolve_tickers(
            asset_names={"존재하지않는종목"},
            ticker_hints={},
        )

    assert result == {"존재하지않는종목": None}


@pytest.mark.asyncio
async def test_parallel_lookup_for_multiple_names():
    """미해결 이름들이 asyncio.gather 로 병렬 조회되어 모두 매핑됨."""
    fake_db = {
        "삼성전자": {"code": "FAKE_SS", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"},
        "카카오": {"code": "FAKE_KAKAO", "name": "카카오", "market": "KR", "exchange": "KOSPI"},
        "없는종목": None,
    }

    async def fake_match(q, **_kw):
        return fake_db.get(q)

    with patch("invest_note_api.broker_import.ticker_resolver.find_first_kr_match", fake_match):
        result = await resolve_tickers(
            asset_names={"삼성전자", "카카오", "없는종목"},
            ticker_hints={},
        )

    assert result == {"삼성전자": "FAKE_SS", "카카오": "FAKE_KAKAO", "없는종목": None}


@pytest.mark.asyncio
async def test_mixed_hints_and_naver_fallback():
    """ticker_hints + Naver fallback 혼합 케이스."""
    async def fake_match(q, **_kw):
        if q == "현대차":
            return {"code": "FAKE_HMC", "name": "현대자동차", "market": "KR", "exchange": "KOSPI"}
        return None

    with patch("invest_note_api.broker_import.ticker_resolver.find_first_kr_match", fake_match):
        result = await resolve_tickers(
            asset_names={"삼성전자", "현대차"},
            ticker_hints={"삼성전자": "005930"},
        )

    assert result == {"삼성전자": "005930", "현대차": "FAKE_HMC"}


@pytest.mark.asyncio
async def test_find_first_query_length_guards():
    """길이 < 2 또는 > MAX_NAME_LEN(50) 이면 search_kr 호출 없이 None."""
    async def boom(_q, **_kw):
        raise AssertionError("search_kr 가 호출됨")

    with patch.object(naver_search, "search_kr", boom):
        assert await naver_search.find_first_kr_match("") is None
        assert await naver_search.find_first_kr_match(" ") is None
        assert await naver_search.find_first_kr_match("A") is None
        assert await naver_search.find_first_kr_match("가" * 51) is None


@pytest.mark.asyncio
async def test_find_first_prefers_exact_match_over_first_result():
    """검색 결과 중 정확일치가 있으면 그것을 우선."""
    async def fake_search(_q, **_kw):
        return [
            {"code": "111", "name": "삼성전자우", "market": "KR", "exchange": "KOSPI"},
            {"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"},
        ]

    with patch.object(naver_search, "search_kr", fake_search):
        match = await naver_search.find_first_kr_match("삼성전자")

    assert match is not None
    assert match["code"] == "005930"


@pytest.mark.asyncio
async def test_find_first_falls_back_to_first_result_when_no_exact():
    """정확일치 없으면 첫 결과 (Naver 자동완성 1순위) 사용."""
    async def fake_search(_q, **_kw):
        return [
            {"code": "005380", "name": "현대자동차", "market": "KR", "exchange": "KOSPI"},
            {"code": "005385", "name": "현대자동차우", "market": "KR", "exchange": "KOSPI"},
        ]

    with patch.object(naver_search, "search_kr", fake_search):
        match = await naver_search.find_first_kr_match("현대차")

    assert match is not None
    assert match["code"] == "005380"


@pytest.mark.asyncio
async def test_find_first_empty_search_returns_none():
    async def fake_search(_q, **_kw):
        return []

    with patch.object(naver_search, "search_kr", fake_search):
        assert await naver_search.find_first_kr_match("없는종목") is None


@pytest.mark.asyncio
async def test_search_kr_filters_non_kr_type_codes():
    """typeCode 가 한국 거래소가 아니면 결과에서 제외."""
    class FakeRes:
        status_code = 200

        @staticmethod
        def json():
            return {
                "items": [
                    {"code": "AAPL", "name": "Apple", "typeCode": "NASDAQ"},
                    {"code": "005930", "name": "삼성전자", "typeCode": "KOSPI"},
                    {"code": "360750", "name": "TIGER 미국S&P500", "typeCode": "ETF"},
                    {"code": "NYSE1", "name": "Foreign Co", "typeCode": "NYSE"},
                ]
            }

    async def fake_get(_client, _q):
        return FakeRes()

    with patch.object(naver_search, "_do_get", fake_get):
        results = await naver_search.search_kr("test")

    codes = [r["code"] for r in results]
    assert codes == ["005930", "360750"]
