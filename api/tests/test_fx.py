"""external.fx — Yahoo 환율 조회 + 캐시 검증."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from invest_note_api.external.fx import (
    FxCacheState,
    _yahoo_fx_symbol,
    get_fx_rate,
    validate_fx_providers,
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
            return await get_fx_rate(fx_state, client=client, providers=["yahoo"])

    assert asyncio.run(runner()) is None


def test_get_fx_rate_falls_back_to_er_api(fx_state: FxCacheState):
    """Yahoo 실패 시 체인이 er_api 로 폴백해 환율을 채운다 — 단일 공급자 SPOF 완화."""
    routes = {
        "https://query2.finance.yahoo.com": httpx.Response(503),
        "https://open.er-api.com/v6/latest/USD": httpx.Response(
            200,
            json={"result": "success", "base_code": "USD", "rates": {"KRW": 1450.25}},
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await get_fx_rate(
                fx_state, client=client, providers=["yahoo", "er_api"]
            )

    result = asyncio.run(runner())
    assert result is not None
    assert result["rate"] == 1450.25
    assert result["base"] == "USD"
    assert result["quote"] == "KRW"


def test_er_api_non_success_result_is_skipped(fx_state: FxCacheState):
    """er_api result!="success" 는 0.0 으로 걸러져 None — 잘못된 환율 박제 방지."""
    routes = {
        "https://query2.finance.yahoo.com": httpx.Response(503),
        "https://open.er-api.com/v6/latest/USD": httpx.Response(
            200, json={"result": "error", "rates": {}}
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await get_fx_rate(
                fx_state, client=client, providers=["yahoo", "er_api"]
            )

    assert asyncio.run(runner()) is None


def test_validate_fx_providers_rejects_unknown_and_empty():
    with pytest.raises(ValueError):
        validate_fx_providers(["yahoo", "bogus"])
    with pytest.raises(ValueError):
        validate_fx_providers([])
    validate_fx_providers(["yahoo", "er_api"])  # 정상 — 예외 없음


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


def _stateful_client(responses: list[httpx.Response]) -> tuple[httpx.AsyncClient, dict]:
    """호출 순서대로 responses 를 소진하는 mock client. 마지막 응답을 반복."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[idx]

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


def test_get_fx_rate_keeps_stale_on_refresh_failure(fx_state: FxCacheState):
    """fetch 실패 시 직전 성공값을 stale 로 유지 — None 을 덮어쓰지 않는다(D2 결정)."""
    ok = httpx.Response(
        200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 1300.0}}]}}
    )
    client, calls = _stateful_client([ok, httpx.Response(503)])

    async def runner():
        async with client:
            # 단일 공급자로 고정 — stale 유지 의미를 폴백 체인과 분리해 검증.
            first = await get_fx_rate(fx_state, client=client, providers=["yahoo"])
            second = await get_fx_rate(
                fx_state, client=client, force_refresh=True, providers=["yahoo"]
            )
            return first, second

    first, second = asyncio.run(runner())
    assert first is not None and first["rate"] == 1300.0
    assert second == first  # 실패 → 직전 성공값 유지
    assert calls["n"] == 2  # force_refresh 가 fast-path 를 우회해 실제 재fetch


def test_get_fx_rate_failure_not_negative_cached(fx_state: FxCacheState):
    """실패(None)는 캐시에 박지 않는다 — 다음 호출이 즉시 재시도(10분 공백 방지)."""
    client, calls = _stateful_client([httpx.Response(503)])

    async def runner():
        async with client:
            a = await get_fx_rate(fx_state, client=client, providers=["yahoo"])
            b = await get_fx_rate(fx_state, client=client, providers=["yahoo"])
            return a, b

    a, b = asyncio.run(runner())
    assert a is None and b is None
    assert calls["n"] == 2  # None 미캐싱 → 매 호출 재fetch
