"""external.quotes _get_cached single-flight 동작 검증."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from invest_note_api.external.quotes import (
    QuoteCacheState,
    _fetch_kr_price,
    _get_cached,
)


@pytest.fixture
def quote_state() -> QuoteCacheState:
    """매 테스트마다 새 인스턴스 — 모듈 globals 없이 자동 격리."""
    return QuoteCacheState()


def test_get_cached_concurrent_calls_invoke_fetch_once(quote_state: QuoteCacheState):
    """동일 키 동시 호출 N건은 fetch_fn을 1번만 실행해야 한다."""
    call_count = 0

    async def slow_fetch():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"price": 100.0, "currency": "KRW", "as_of": "now"}

    async def runner():
        return await asyncio.gather(*[
            _get_cached(quote_state, "KR:005930", slow_fetch) for _ in range(5)
        ])

    results = asyncio.run(runner())

    assert call_count == 1
    assert all(r == {"price": 100.0, "currency": "KRW", "as_of": "now"} for r in results)


def test_get_cached_serves_from_cache_after_first_call(quote_state: QuoteCacheState):
    """캐시 hit 시 fetch_fn 미실행."""
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        return {"price": 50.0, "currency": "KRW", "as_of": "now"}

    async def runner():
        first = await _get_cached(quote_state, "KR:000660", fetch)
        second = await _get_cached(quote_state, "KR:000660", fetch)
        return first, second

    first, second = asyncio.run(runner())

    assert call_count == 1
    assert first == second


def test_get_cached_propagates_exception_and_clears_inflight(quote_state: QuoteCacheState):
    """fetch 실패 시 followers에게 예외 전파 + inflight 정리."""

    async def failing_fetch():
        raise RuntimeError("boom")

    async def runner():
        with pytest.raises(RuntimeError, match="boom"):
            await asyncio.gather(*[
                _get_cached(quote_state, "KR:fail", failing_fetch) for _ in range(3)
            ])

    asyncio.run(runner())

    assert "KR:fail" not in quote_state.inflight


def _build_mock_client(routes: dict[str, httpx.Response | Exception]) -> httpx.AsyncClient:
    """URL prefix → response/exception 매핑. prefix 미매칭은 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for prefix, resp in routes.items():
            if url.startswith(prefix):
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_fetch_kr_price_falls_back_to_yahoo_kospi_when_naver_fails():
    """Naver 양쪽 endpoint 실패 → Yahoo .KS 에서 시세 회수."""
    routes = {
        "https://polling.finance.naver.com": httpx.Response(503),
        "https://api.stock.naver.com": httpx.Response(503),
        "https://query2.finance.yahoo.com/v8/finance/chart/005930.KS": httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"regularMarketPrice": 71000}}]}},
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "005930")

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 71000.0
    assert result["currency"] == "KRW"


def test_fetch_kr_price_falls_back_to_yahoo_kosdaq_when_kospi_empty():
    """Yahoo .KS 가 빈 result(잘못된 시장) → .KQ 로 재시도."""
    routes = {
        "https://polling.finance.naver.com": httpx.Response(503),
        "https://api.stock.naver.com": httpx.Response(503),
        "https://query2.finance.yahoo.com/v8/finance/chart/247540.KS": httpx.Response(
            200, json={"chart": {"result": []}}
        ),
        "https://query2.finance.yahoo.com/v8/finance/chart/247540.KQ": httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"regularMarketPrice": 42000}}]}},
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "247540")

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 42000.0


def test_fetch_kr_price_returns_none_when_all_sources_fail():
    """Naver + Yahoo .KS/.KQ 모두 실패 → None."""
    routes = {
        "https://polling.finance.naver.com": httpx.Response(503),
        "https://api.stock.naver.com": httpx.Response(503),
        "https://query2.finance.yahoo.com": httpx.Response(503),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "999999")

    assert asyncio.run(runner()) is None


def test_fetch_kr_price_prefers_naver_when_available():
    """Naver realtime 성공 시 Yahoo 호출되지 않아야 한다."""
    yahoo_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal yahoo_called
        url = str(request.url)
        if url.startswith("https://polling.finance.naver.com"):
            return httpx.Response(200, json={"datas": [{"closePriceRaw": "71500"}]})
        if url.startswith("https://query2.finance.yahoo.com"):
            yahoo_called = True
        return httpx.Response(404)

    async def runner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _fetch_kr_price(client, "005930")

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 71500.0
    assert yahoo_called is False
