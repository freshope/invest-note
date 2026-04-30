"""external.quotes _get_cached single-flight 동작 검증."""
from __future__ import annotations

import asyncio

import pytest

from invest_note_api.external import quotes


@pytest.fixture(autouse=True)
def clear_cache():
    quotes._cache.clear()
    quotes._inflight.clear()
    yield
    quotes._cache.clear()
    quotes._inflight.clear()


def test_get_cached_concurrent_calls_invoke_fetch_once():
    """동일 키 동시 호출 N건은 fetch_fn을 1번만 실행해야 한다."""
    call_count = 0

    async def slow_fetch():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"price": 100.0, "currency": "KRW", "as_of": "now"}

    async def runner():
        results = await asyncio.gather(*[
            quotes._get_cached("KR:005930", slow_fetch) for _ in range(5)
        ])
        return results

    results = asyncio.run(runner())

    assert call_count == 1
    assert all(r == {"price": 100.0, "currency": "KRW", "as_of": "now"} for r in results)


def test_get_cached_serves_from_cache_after_first_call():
    """캐시 hit 시 fetch_fn 미실행."""
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        return {"price": 50.0, "currency": "KRW", "as_of": "now"}

    async def runner():
        first = await quotes._get_cached("KR:000660", fetch)
        second = await quotes._get_cached("KR:000660", fetch)
        return first, second

    first, second = asyncio.run(runner())

    assert call_count == 1
    assert first == second


def test_get_cached_propagates_exception_and_clears_inflight():
    """fetch 실패 시 followers에게 예외 전파 + inflight 정리."""

    async def failing_fetch():
        raise RuntimeError("boom")

    async def runner():
        with pytest.raises(RuntimeError, match="boom"):
            await asyncio.gather(*[
                quotes._get_cached("KR:fail", failing_fetch) for _ in range(3)
            ])

    asyncio.run(runner())

    assert "KR:fail" not in quotes._inflight
