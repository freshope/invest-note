"""ticker_resolver(로컬 stocks 매칭) + naver_search(seed enrichment 용) 단위 테스트."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from invest_note_api.broker_import.ticker_resolver import resolve_tickers
from invest_note_api.external import naver_search


def _patch_lookup(fake_db: dict[str, dict]):
    """stocks_repo.lookup_by_names 대체 — 매칭된 이름만 담은 dict 반환(미해결은 키 없음)."""
    async def fake_lookup(_conn, names, **_kw):
        return {n: fake_db[n] for n in names if n in fake_db}

    return patch("invest_note_api.db_ops.stocks_repo.lookup_by_names", fake_lookup)


@pytest.mark.asyncio
async def test_ticker_hint_provides_code_lookup_provides_exchange():
    """ticker_hints 의 코드는 권위로 쓰되, exchange 는 로컬 매칭에서 채운다."""
    fake_db = {"삼성전자": {"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"}}

    with _patch_lookup(fake_db):
        result = await resolve_tickers(
            asset_names={"삼성전자"},
            ticker_hints={"삼성전자": "005930"},
            conn=None,
        )

    assert result == {"삼성전자": {"code": "005930", "exchange": "KOSPI"}}


@pytest.mark.asyncio
async def test_ticker_hint_keeps_code_when_lookup_misses():
    """hint 코드가 있는데 로컬 매칭이 없으면 code 는 유지, exchange 만 빈 값."""
    with _patch_lookup({}):
        result = await resolve_tickers(
            asset_names={"삼성전자"},
            ticker_hints={"삼성전자": "005930"},
            conn=None,
        )

    assert result == {"삼성전자": {"code": "005930", "exchange": ""}}


@pytest.mark.asyncio
async def test_lookup_match_short_alias():
    """약칭 '현대차' → 로컬 별칭 매칭 '현대자동차' (code + exchange)."""
    fake_db = {"현대차": {"code": "005380", "name": "현대자동차", "market": "KR", "exchange": "KOSPI"}}

    with _patch_lookup(fake_db):
        result = await resolve_tickers(asset_names={"현대차"}, ticker_hints={}, conn=None)

    assert result == {"현대차": {"code": "005380", "exchange": "KOSPI"}}


@pytest.mark.asyncio
async def test_lookup_match_etf_full_name():
    """ETF 정확명 'TIGER 미국S&P500' → code + exchange 매핑 검증."""
    fake_db = {"TIGER 미국S&P500": {"code": "360750", "name": "TIGER 미국S&P500", "market": "KR", "exchange": "ETF"}}

    with _patch_lookup(fake_db):
        result = await resolve_tickers(asset_names={"TIGER 미국S&P500"}, ticker_hints={}, conn=None)

    assert result == {"TIGER 미국S&P500": {"code": "360750", "exchange": "ETF"}}


@pytest.mark.asyncio
async def test_lookup_no_match_returns_none():
    """로컬 매칭 없으면 미해결 (None)."""
    with _patch_lookup({}):
        result = await resolve_tickers(asset_names={"존재하지않는종목"}, ticker_hints={}, conn=None)

    assert result == {"존재하지않는종목": None}


@pytest.mark.asyncio
async def test_lookup_for_multiple_names():
    """여러 이름이 한 번의 lookup_by_names 로 조회되어 매핑됨(미해결은 None)."""
    fake_db = {
        "삼성전자": {"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"},
        "카카오": {"code": "035720", "name": "카카오", "market": "KR", "exchange": "KOSPI"},
    }

    with _patch_lookup(fake_db):
        result = await resolve_tickers(
            asset_names={"삼성전자", "카카오", "없는종목"},
            ticker_hints={},
            conn=None,
        )

    assert result == {
        "삼성전자": {"code": "005930", "exchange": "KOSPI"},
        "카카오": {"code": "035720", "exchange": "KOSPI"},
        "없는종목": None,
    }


@pytest.mark.asyncio
async def test_mixed_hints_and_lookup():
    """ticker_hints(코드 권위) + 로컬 매칭(exchange) 혼합 케이스."""
    fake_db = {
        "현대차": {"code": "005380", "name": "현대자동차", "market": "KR", "exchange": "KOSPI"},
        "삼성전자": {"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"},
    }

    with _patch_lookup(fake_db):
        result = await resolve_tickers(
            asset_names={"삼성전자", "현대차"},
            ticker_hints={"삼성전자": "005930"},
            conn=None,
        )

    assert result == {
        "삼성전자": {"code": "005930", "exchange": "KOSPI"},
        "현대차": {"code": "005380", "exchange": "KOSPI"},
    }


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
