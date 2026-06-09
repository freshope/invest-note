"""external.fx — Yahoo 환율 조회 + 캐시 검증."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from invest_note_api.external.fx import (
    FxCacheState,
    _yahoo_fx_symbol,
    get_fx_rate,
)


@pytest.fixture
def fx_state() -> FxCacheState:
    return FxCacheState()


def _build_mock_client(
    routes: dict[str, httpx.Response | Exception],
) -> httpx.AsyncClient:
    """URL prefix → response/exception 매핑. 미매칭은 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for prefix, resp in routes.items():
            if url.startswith(prefix):
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_yahoo_fx_symbol_usd_base_uses_quote_only():
    assert _yahoo_fx_symbol("USD", "KRW") == "KRW=X"


def test_yahoo_fx_symbol_non_usd_base_concatenates():
    assert _yahoo_fx_symbol("EUR", "KRW") == "EURKRW=X"


def test_get_fx_rate_returns_usdkrw(fx_state: FxCacheState):
    routes = {
        "https://query2.finance.yahoo.com/v8/finance/chart/KRW=X": httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"regularMarketPrice": 1350.5}}]}},
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await get_fx_rate(fx_state, client=client, base="USD", quote="KRW")

    result = asyncio.run(runner())
    assert result is not None
    assert result["rate"] == 1350.5
    assert result["base"] == "USD"
    assert result["quote"] == "KRW"


def test_get_fx_rate_serves_from_cache(fx_state: FxCacheState):
    """캐시 hit 시 외부 호출 미발생."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"regularMarketPrice": 1300.0}}]}},
        )

    async def runner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            first = await get_fx_rate(fx_state, client=client)
            second = await get_fx_rate(fx_state, client=client)
            return first, second

    first, second = asyncio.run(runner())
    assert call_count == 1
    assert first == second
    assert first is not None and first["rate"] == 1300.0


def test_get_fx_rate_force_refresh_bypasses_cache(fx_state: FxCacheState):
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"regularMarketPrice": 1300.0}}]}},
        )

    async def runner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await get_fx_rate(fx_state, client=client)
            await get_fx_rate(fx_state, client=client, force_refresh=True)

    asyncio.run(runner())
    assert call_count == 2


def test_get_fx_rate_returns_none_on_failure(fx_state: FxCacheState):
    routes = {"https://query2.finance.yahoo.com": httpx.Response(503)}

    async def runner():
        async with _build_mock_client(routes) as client:
            return await get_fx_rate(fx_state, client=client)

    assert asyncio.run(runner()) is None


def test_get_fx_rate_returns_none_on_empty_result(fx_state: FxCacheState):
    routes = {
        "https://query2.finance.yahoo.com": httpx.Response(
            200, json={"chart": {"result": []}}
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await get_fx_rate(fx_state, client=client)

    assert asyncio.run(runner()) is None
