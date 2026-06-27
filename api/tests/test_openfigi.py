"""external/openfigi.py — ISIN→ticker 페처 단위 테스트(httpx mock)."""

from __future__ import annotations

import httpx
import pytest

from invest_note_api.external import openfigi
from invest_note_api.external.openfigi import map_isins


def _mock_client(handler) -> httpx.AsyncClient:
    """MockTransport 로 OpenFIGI 응답을 가짜로 돌려주는 AsyncClient."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_maps_isin_to_us_ticker():
    """단일 ISIN → 미국 거래소 ticker 추출."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "data": [
                        {
                            "ticker": "PLTR",
                            "exchCode": "UN",
                            "name": "PALANTIR TECHNOLOGIES INC",
                            "securityType": "Common Stock",
                        }
                    ]
                }
            ],
        )

    async with _mock_client(handler) as client:
        result = await map_isins(["US69608A1088"], client=client)

    assert result == {
        "US69608A1088": {
            "ticker": "PLTR",
            "exch_code": "UN",
            "name": "PALANTIR TECHNOLOGIES INC",
            "security_type": "Common Stock",
        }
    }


@pytest.mark.asyncio
async def test_prefers_us_common_stock_among_multiple():
    """다건 매칭 시 미국 거래소 + 보통주 우선."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "data": [
                        {"ticker": "PLTR", "exchCode": "GR", "name": "X", "securityType": "Common Stock"},
                        {"ticker": "PLTR", "exchCode": "UW", "name": "PALANTIR", "securityType": "Common Stock"},
                        {"ticker": "PLTRW", "exchCode": "UN", "name": "PALANTIR WT", "securityType": "Warrant"},
                    ]
                }
            ],
        )

    async with _mock_client(handler) as client:
        result = await map_isins(["US69608A1088"], client=client)

    chosen = result["US69608A1088"]
    assert chosen is not None
    assert chosen["ticker"] == "PLTR"
    assert chosen["exch_code"] == "UW"


@pytest.mark.asyncio
async def test_unresolved_isin_returns_none():
    """OpenFIGI 가 data 없이 warning/error 만 주면 미해결(None)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"warning": "No identifier found."}])

    async with _mock_client(handler) as client:
        result = await map_isins(["XX0000000000"], client=client)

    assert result == {"XX0000000000": None}


@pytest.mark.asyncio
async def test_network_error_is_graceful():
    """네트워크 예외는 삼키고 미해결 처리 — import 전체 실패 금지."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    async with _mock_client(handler) as client:
        result = await map_isins(["US69608A1088"], client=client)

    assert result == {"US69608A1088": None}


@pytest.mark.asyncio
async def test_non_200_is_graceful():
    """non-200(예: 500)도 미해결 처리."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    async with _mock_client(handler) as client:
        result = await map_isins(["US69608A1088"], client=client)

    assert result == {"US69608A1088": None}


@pytest.mark.asyncio
async def test_dedupes_input_isins():
    """중복 ISIN 은 한 번만 조회(요청 jobs 에 유니크 ISIN 만)."""
    seen_jobs: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen_jobs.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=[{"data": [{"ticker": "PLTR", "exchCode": "UN", "name": "P", "securityType": "Common Stock"}]}],
        )

    async with _mock_client(handler) as client:
        result = await map_isins(["US69608A1088", "US69608A1088"], client=client)

    assert len(seen_jobs) == 1
    assert seen_jobs[0] == [{"idType": "ID_ISIN", "idValue": "US69608A1088"}]
    assert set(result.keys()) == {"US69608A1088"}


@pytest.mark.asyncio
async def test_empty_input_skips_call():
    """빈 입력이면 OpenFIGI 호출 없이 빈 dict."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("호출되면 안 됨")

    async with _mock_client(handler) as client:
        result = await map_isins([], client=client)

    assert result == {}


@pytest.mark.asyncio
async def test_api_key_sets_header():
    """api_key 지정 시 X-OPENFIGI-APIKEY 헤더 전송."""
    seen_headers: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers.get("X-OPENFIGI-APIKEY"))
        return httpx.Response(
            200,
            json=[{"data": [{"ticker": "PLTR", "exchCode": "UN", "name": "P", "securityType": "Common Stock"}]}],
        )

    async with _mock_client(handler) as client:
        await map_isins(["US69608A1088"], api_key="secret", client=client)

    assert seen_headers == ["secret"]


@pytest.mark.asyncio
async def test_multi_batch_no_key_paces_between_batches(monkeypatch):
    """무키 배치 크기 10 초과 시 2개 배치로 나뉘고 배치 사이에만 sleep(1회)."""
    sleeps: list = []

    async def fake_sleep(secs):
        sleeps.append(secs)

    monkeypatch.setattr(openfigi.asyncio, "sleep", fake_sleep)

    request_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        jobs = json.loads(request.content)
        request_count["n"] += 1
        return httpx.Response(
            200,
            json=[
                {"data": [{"ticker": j["idValue"][:4], "exchCode": "UN", "name": "X", "securityType": "Common Stock"}]}
                for j in jobs
            ],
        )

    isins = [f"US{i:010d}" for i in range(15)]  # 15건 → 무키 배치 10 → 2 배치
    async with _mock_client(handler) as client:
        result = await map_isins(isins, client=client)

    assert request_count["n"] == 2
    assert len(sleeps) == 1  # 배치 사이 1회만
    assert len(result) == 15
