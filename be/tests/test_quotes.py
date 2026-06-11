"""external.quotes _get_cached single-flight 동작 검증."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from invest_note_api.external.quotes import (
    QuoteCacheState,
    _fetch_kr_price,
    _fetch_yahoo_us,
    _get_cached,
    _to_yahoo_us_symbol,
    fetch_quotes_by_keys,
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


def test_fetch_kr_price_extracts_traded_on_from_realtime():
    """Naver realtime localTradedAt → traded_on(KST 날짜) — 휴장일 판정 신호."""
    routes = {
        "https://polling.finance.naver.com": httpx.Response(
            200,
            json={"datas": [{"closePriceRaw": "71500", "localTradedAt": "2026-06-05T15:30:00+09:00"}]},
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "005930")

    result = asyncio.run(runner())
    assert result is not None
    assert result["traded_on"] == "2026-06-05"


def test_fetch_kr_price_yahoo_traded_on_from_epoch():
    """Yahoo regularMarketTime(epoch) → KST 날짜로 변환. 필드 없으면 None."""
    from datetime import datetime

    ts = int(datetime.fromisoformat("2026-06-05T15:30:00+09:00").timestamp())
    routes = {
        "https://polling.finance.naver.com": httpx.Response(503),
        "https://api.stock.naver.com": httpx.Response(503),
        "https://query2.finance.yahoo.com/v8/finance/chart/005930.KS": httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"regularMarketPrice": 71000, "regularMarketTime": ts}}]}},
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "005930")

    result = asyncio.run(runner())
    assert result is not None
    assert result["traded_on"] == "2026-06-05"


def test_fetch_kr_price_traded_on_none_when_source_lacks_field():
    """체결 일시 필드가 없는 응답 → traded_on=None (라우터 fallback 경로)."""
    routes = {
        "https://polling.finance.naver.com": httpx.Response(
            200, json={"datas": [{"closePriceRaw": "71500"}]}
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "005930")

    result = asyncio.run(runner())
    assert result is not None
    assert result["traded_on"] is None


def test_fetch_kr_price_providers_yahoo_only_skips_naver():
    """providers=["yahoo"] → Naver 엔드포인트 미호출, Yahoo 단독 시도."""
    naver_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal naver_called
        url = str(request.url)
        if "naver.com" in url:
            naver_called = True
            return httpx.Response(200, json={"datas": [{"closePriceRaw": "1"}]})
        if url.startswith("https://query2.finance.yahoo.com/v8/finance/chart/005930.KS"):
            return httpx.Response(
                200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 71000}}]}}
            )
        return httpx.Response(404)

    async def runner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _fetch_kr_price(client, "005930", ["yahoo"])

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 71000.0
    assert naver_called is False


def test_fetch_kr_price_providers_order_reversed():
    """providers=["yahoo","naver"] → yahoo 성공 시 naver 미호출 (체인 순서가 env 를 따름)."""
    naver_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal naver_called
        url = str(request.url)
        if "naver.com" in url:
            naver_called = True
            return httpx.Response(200, json={"datas": [{"closePriceRaw": "1"}]})
        if url.startswith("https://query2.finance.yahoo.com/v8/finance/chart/005930.KS"):
            return httpx.Response(
                200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 70000}}]}}
            )
        return httpx.Response(404)

    async def runner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _fetch_kr_price(client, "005930", ["yahoo", "naver"])

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 70000.0
    assert naver_called is False


def test_fetch_kr_price_unknown_provider_raises_value_error():
    """registry 에 없는 공급자명 → ValueError (env 오타 fail-fast)."""

    async def runner():
        async with _build_mock_client({}) as client:
            return await _fetch_kr_price(client, "005930", ["naverr"])

    with pytest.raises(ValueError, match="quotes"):
        asyncio.run(runner())


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


# ---- KIS 공급자 ----

KIS_BASE = "https://openapi.koreainvestment.com:9443"


@pytest.fixture
def kis_configured(monkeypatch):
    """KIS 자격증명이 설정된 모듈 싱글톤 — monkeypatch 로 테스트 후 자동 복원."""
    from invest_note_api.external import kis

    monkeypatch.setattr(kis, "_state", kis.KisState(app_key="key", app_secret="secret"))


def test_fetch_kr_price_kis_success(kis_configured):
    """providers=["kis"] — 토큰 발급 후 현재가(stck_prpr) 회수. traded_on 은 None."""
    routes = {
        f"{KIS_BASE}/oauth2/tokenP": httpx.Response(
            200, json={"access_token": "tok-1", "expires_in": 86400}
        ),
        f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-price": httpx.Response(
            200, json={"rt_cd": "0", "output": {"stck_prpr": "71000"}}
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "005930", ["kis"])

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 71000.0
    assert result["currency"] == "KRW"
    assert result["traded_on"] is None


def test_fetch_kr_price_kis_error_falls_back_to_naver(kis_configured):
    """KIS 오류 응답(rt_cd!=0) → 체인의 다음 공급자(naver)로 fallback."""
    routes = {
        f"{KIS_BASE}/oauth2/tokenP": httpx.Response(
            200, json={"access_token": "tok-1", "expires_in": 86400}
        ),
        f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-price": httpx.Response(
            200, json={"rt_cd": "1", "msg_cd": "EGW00121", "msg1": "err"}
        ),
        "https://polling.finance.naver.com": httpx.Response(
            200, json={"datas": [{"closePriceRaw": "71500"}]}
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_kr_price(client, "005930", ["kis", "naver"])

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 71500.0


def test_fetch_kr_price_kis_unconfigured_falls_back_without_network(monkeypatch):
    """자격증명 미설정 → KIS 네트워크 호출 없이 다음 공급자로 즉시 fallback."""
    from invest_note_api.external import kis

    monkeypatch.setattr(kis, "_state", kis.KisState())
    kis_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal kis_called
        url = str(request.url)
        if url.startswith(KIS_BASE):
            kis_called = True
            return httpx.Response(500)
        if url.startswith("https://polling.finance.naver.com"):
            return httpx.Response(200, json={"datas": [{"closePriceRaw": "71500"}]})
        return httpx.Response(404)

    async def runner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _fetch_kr_price(client, "005930", ["kis", "naver"])

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 71500.0
    assert kis_called is False


# ─────────────────────────── US(해외) 시세 ───────────────────────────


def test_fetch_yahoo_us_returns_price_and_currency_from_meta():
    """suffix 없는 티커 → Yahoo chart. price + meta.currency 사용."""
    routes = {
        "https://query2.finance.yahoo.com/v8/finance/chart/AAPL": httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"regularMarketPrice": 195.5, "currency": "USD"}}]}},
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_yahoo_us(client, "AAPL")

    result = asyncio.run(runner())
    assert result is not None
    assert result["price"] == 195.5
    assert result["currency"] == "USD"


def test_fetch_yahoo_us_defaults_currency_to_usd_when_missing():
    routes = {
        "https://query2.finance.yahoo.com/v8/finance/chart/AAPL": httpx.Response(
            200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 100.0}}]}}
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_yahoo_us(client, "AAPL")

    result = asyncio.run(runner())
    assert result is not None
    assert result["currency"] == "USD"


def test_fetch_yahoo_us_returns_none_on_empty_or_failure():
    routes = {"https://query2.finance.yahoo.com": httpx.Response(503)}

    async def runner():
        async with _build_mock_client(routes) as client:
            return await _fetch_yahoo_us(client, "NOPE")

    assert asyncio.run(runner()) is None


def test_to_yahoo_us_symbol_converts_class_and_preferred():
    """보통주 no-op, 클래스주 `.`→`-`, 우선주 `$`→`-P` ($ 먼저, . 나중)."""
    assert _to_yahoo_us_symbol("AAPL") == "AAPL"
    assert _to_yahoo_us_symbol("BRK.B") == "BRK-B"
    assert _to_yahoo_us_symbol("BAC$B") == "BAC-PB"


def test_fetch_yahoo_us_accepts_whitelisted_tickers():
    """허용 티커(영숫자/`.`/`$`/`-`)는 통과 — 화이트리스트 가드가 정상 시세를 막지 않는다.

    seed 표기(`.`/`$`)는 Yahoo 표기로 변환돼 요청되므로 route key 도 변환형을 쓴다.
    """
    for code in ("AAPL", "BRK.B", "BRK-B", "RDS.A", "BAC$B"):
        routes = {
            f"https://query2.finance.yahoo.com/v8/finance/chart/{_to_yahoo_us_symbol(code)}": httpx.Response(
                200,
                json={"chart": {"result": [{"meta": {"regularMarketPrice": 10.0, "currency": "USD"}}]}},
            ),
        }

        async def runner():
            async with _build_mock_client(routes) as client:
                return await _fetch_yahoo_us(client, code)

        result = asyncio.run(runner())
        assert result is not None, code
        assert result["price"] == 10.0


def test_fetch_yahoo_us_converts_seed_symbol_in_request_url():
    """seed 표기 BRK.B 입력 → Yahoo URL 은 변환된 BRK-B(원본 BRK.B 미전송)."""
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(
            200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 10.0}}]}}
        )

    async def runner():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _fetch_yahoo_us(client, "BRK.B")

    result = asyncio.run(runner())
    assert result is not None
    assert "/chart/BRK-B" in captured["url"]
    assert "BRK.B" not in captured["url"]


def test_fetch_yahoo_us_rejects_path_manipulating_tickers():
    """`/`·`?`·`#`·공백 등 화이트리스트 위반 심볼은 HTTP 전송 없이 None(graceful)."""
    called = {"hit": False}

    def handler(_req: httpx.Request) -> httpx.Response:
        called["hit"] = True
        return httpx.Response(200, json={})

    async def runner(code: str):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _fetch_yahoo_us(client, code)

    for bad in ("AAPL/../foo", "AAPL?x=1", "AAPL#frag", "AAPL BBB", "", "A" * 21):
        assert asyncio.run(runner(bad)) is None, bad
    assert called["hit"] is False, "위반 심볼인데 HTTP 요청이 전송됨"


def test_fetch_quotes_by_keys_routes_us_to_yahoo_and_kr_to_chain():
    """KR→공급자 체인(naver fail→yahoo .KS), US→yahoo bare ticker. 통화 분리 유지."""
    state = QuoteCacheState()
    routes = {
        "https://polling.finance.naver.com": httpx.Response(503),
        "https://api.stock.naver.com": httpx.Response(503),
        "https://query2.finance.yahoo.com/v8/finance/chart/005930.KS": httpx.Response(
            200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 71000, "currency": "KRW"}}]}}
        ),
        "https://query2.finance.yahoo.com/v8/finance/chart/AAPL": httpx.Response(
            200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 195.5, "currency": "USD"}}]}}
        ),
    }

    async def runner():
        async with _build_mock_client(routes) as client:
            return await fetch_quotes_by_keys(
                state, ["005930:KR", "AAPL:US"], client=client, providers=["naver", "yahoo"]
            )

    out = asyncio.run(runner())
    assert out["005930:KR"]["price"] == 71000.0
    assert out["005930:KR"]["currency"] == "KRW"
    assert out["AAPL:US"]["price"] == 195.5
    assert out["AAPL:US"]["currency"] == "USD"


def test_fetch_quotes_by_keys_unsupported_country_is_null():
    """공급자 없는 국가(OTHER) → null."""
    state = QuoteCacheState()
    routes = {"https://query2.finance.yahoo.com": httpx.Response(503)}

    async def runner():
        async with _build_mock_client(routes) as client:
            return await fetch_quotes_by_keys(
                state, ["XYZ:OTHER"], client=client, providers=["yahoo"]
            )

    out = asyncio.run(runner())
    assert out["XYZ:OTHER"] is None


# ──────────────── stale-유지 (D2-1: 시세 SPOF 완화) ────────────────


def test_get_cached_serves_stale_when_refetch_fails(quote_state: QuoteCacheState):
    """① 1차 성공→캐시. 직전값 유지하며 실패 fetch → 직전 성공값을 stale 로 반환.

    캐시 엔트리가 살아 있는 동안(force_refresh 로 fetch_fn 재실행) 실패하면 None 으로
    덮지 않고 직전 성공값을 유지한다 — 현재·후속 호출자 모두 stale 을 받는다.
    """

    async def ok_fetch():
        return {"price": 195.5, "currency": "USD", "as_of": "t0"}

    async def fail_fetch():
        return None

    async def runner():
        first = await _get_cached(quote_state, "AAPL:US", ok_fetch)
        # force_refresh 로 fetch_fn 재실행 → 실패. 직전값 stale 유지.
        staled = await _get_cached(quote_state, "AAPL:US", fail_fetch, force_refresh=True)
        return first, staled

    first, staled = asyncio.run(runner())
    assert first == {"price": 195.5, "currency": "USD", "as_of": "t0"}
    assert staled == first  # None 으로 덮이지 않고 직전 성공값 유지


def test_get_cached_failure_with_no_prior_stays_none(quote_state: QuoteCacheState):
    """② 직전 성공값이 없는(원래 시세 없는) 종목은 실패해도 계속 None — 영향 없음.

    또한 None 을 캐시에 박지 않아 다음 호출이 재시도(45s 갇힘 없음)된다.
    """
    call_count = 0

    async def fail_fetch():
        nonlocal call_count
        call_count += 1
        return None

    async def runner():
        first = await _get_cached(quote_state, "NOPE:US", fail_fetch)
        second = await _get_cached(quote_state, "NOPE:US", fail_fetch)  # 캐시 hit 아님 → 재시도
        return first, second

    first, second = asyncio.run(runner())
    assert first is None
    assert second is None
    assert call_count == 2  # None 미캐싱 → 매 호출 재시도


def test_get_cached_force_refresh_failure_keeps_prior(quote_state: QuoteCacheState):
    """③ force_refresh(pull-to-refresh) 로 재요청했는데 실패 → 직전 성공값 유지.

    동시 후속 호출자도 같은 stale 값을 공유(single-flight)한다.
    """

    async def ok_fetch():
        return {"price": 100.0, "currency": "USD", "as_of": "t0"}

    async def fail_fetch():
        await asyncio.sleep(0.01)
        return None

    async def runner():
        await _get_cached(quote_state, "MSFT:US", ok_fetch)
        # force_refresh 5건 동시 — single-flight 로 fail_fetch 1회만, 모두 stale 공유.
        return await asyncio.gather(*[
            _get_cached(quote_state, "MSFT:US", fail_fetch, force_refresh=True)
            for _ in range(5)
        ])

    results = asyncio.run(runner())
    assert all(r == {"price": 100.0, "currency": "USD", "as_of": "t0"} for r in results)
