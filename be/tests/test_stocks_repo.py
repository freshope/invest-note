"""stocks_repo 단위 테스트 — 검색 가드/파라미터/row 매핑 (SQL 자체는 통합 검증)."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock

import pytest

from invest_note_api.db_ops import stocks_repo


@pytest.mark.asyncio
async def test_search_empty_query_skips_db():
    conn = AsyncMock()
    assert await stocks_repo.search(conn, "  ") == []
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_search_single_char_hits_db_by_default():
    """인터랙티브 검색은 1글자 prefix 도 허용(기존 Naver 동작 유지)."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    await stocks_repo.search(conn, "삼")
    conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_search_min_len_2_skips_single_char():
    """import 자동매칭 경로(min_len=2)는 1글자 입력을 가드(오매칭 방지)."""
    conn = AsyncMock()
    assert await stocks_repo.search(conn, "삼", min_len=2) == []
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_search_too_long_query_skips_db():
    conn = AsyncMock()
    assert await stocks_repo.search(conn, "가" * 51) == []
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_search_maps_market_to_exchange():
    """결과 exchange 는 stocks.market(보드) 에서 와야 한다 (Naver shape 유지)."""
    conn = AsyncMock()
    conn.fetch.return_value = [
        {"ticker": "005930", "asset_name": "삼성전자", "country_code": "KR", "market": "KOSPI"}
    ]
    res = await stocks_repo.search(conn, "삼성")
    assert res == [{"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"}]


@pytest.mark.asyncio
async def test_search_passes_chosung_flag_true_for_jamo_query():
    conn = AsyncMock()
    conn.fetch.return_value = []
    await stocks_repo.search(conn, "ㅅㅅㅈㅈ")
    is_cho = conn.fetch.call_args.args[4]
    assert is_cho is True


@pytest.mark.asyncio
async def test_search_escapes_like_wildcards():
    conn = AsyncMock()
    conn.fetch.return_value = []
    await stocks_repo.search(conn, "삼성%_")
    args = conn.fetch.call_args.args
    assert args[4] is False  # is_chosung
    assert args[5] == "삼성\\%\\_"  # escaped like term


@pytest.mark.asyncio
async def test_fetch_meta_empty_codes_skips_db():
    conn = AsyncMock()
    assert await stocks_repo.fetch_meta(conn, []) == {}
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_meta_maps_rows_by_ticker():
    """row→snake_case dict, nps_as_of isoformat, null marcap/nps 유지, 키=ticker."""
    conn = AsyncMock()
    conn.fetch.return_value = [
        {"ticker": "005930", "market": "KOSPI", "marcap_rank": 1,
         "nps_holding": "major", "nps_as_of": datetime.date(2026, 3, 31)},
        {"ticker": "069500", "market": "ETF", "marcap_rank": None,
         "nps_holding": None, "nps_as_of": None},
    ]
    res = await stocks_repo.fetch_meta(conn, ["005930", "069500"])
    assert res == {
        "005930": {"market": "KOSPI", "marcap_rank": 1, "nps_holding": "major", "nps_as_of": "2026-03-31"},
        "069500": {"market": "ETF", "marcap_rank": None, "nps_holding": None, "nps_as_of": None},
    }


@pytest.mark.asyncio
async def test_lookup_by_names_collects_top_match():
    conn = AsyncMock()
    # search 는 이름마다 1건씩 fetch — 첫 이름 매칭, 둘째 이름 미매칭(빈 결과)
    conn.fetch.side_effect = [
        [{"ticker": "005930", "asset_name": "삼성전자", "country_code": "KR", "market": "KOSPI"}],
        [],
    ]
    res = await stocks_repo.lookup_by_names(conn, ["삼성전자", "없는종목"])
    assert res == {"삼성전자": {"code": "005930", "name": "삼성전자", "market": "KR", "exchange": "KOSPI"}}
