"""naver_search.find_overseas_korean_name — US 종목 한글명 조회 파싱/게이팅.

네트워크는 httpx.MockTransport 로 차단. 픽스처는 실제 Naver 자동완성 응답 shape 사용
(code/name/typeCode/nationCode) — 합성 행이 아니라 실응답으로 파싱·게이팅 검증.
"""
from __future__ import annotations

import httpx
import pytest

from invest_note_api.external import naver_search

# 실제 ac.stock.naver.com/ac?q=애플 응답(축약 없이 핵심 항목). AAPL 정확매칭이 동음이의
# (AFL='애플락', APLE='애플 호스피탤리티')·일본 거래소(TOKYO/JPN)를 제치고 선택돼야 한다.
_AAPL_ITEMS = [
    {"code": "AAPL", "name": "애플", "typeCode": "NASDAQ", "nationCode": "USA"},
    {"code": "AFL", "name": "애플락", "typeCode": "NYSE", "nationCode": "USA"},
    {"code": "APLE", "name": "애플 호스피탤리티 리츠", "typeCode": "NYSE", "nationCode": "USA"},
    {"code": "164A", "name": "애플파크", "typeCode": "TOKYO", "nationCode": "JPN"},
]


def _client(items: list[dict], status: int = 200) -> httpx.AsyncClient:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"items": items})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_returns_korean_name_for_exact_ticker_match():
    async with _client(_AAPL_ITEMS) as client:
        assert await naver_search.find_overseas_korean_name("AAPL", client=client) == "애플"


async def test_ignores_case_and_whitespace_in_ticker():
    async with _client(_AAPL_ITEMS) as client:
        assert await naver_search.find_overseas_korean_name(" aapl ", client=client) == "애플"


async def test_rejects_kr_exchange_type_code():
    items = [{"code": "AAPL", "name": "애플", "typeCode": "KOSPI", "nationCode": "USA"}]
    async with _client(items) as client:
        assert await naver_search.find_overseas_korean_name("AAPL", client=client) is None


async def test_rejects_english_only_name():
    items = [{"code": "ZZZ", "name": "Zzz Holdings Inc.", "typeCode": "NASDAQ", "nationCode": "USA"}]
    async with _client(items) as client:
        assert await naver_search.find_overseas_korean_name("ZZZ", client=client) is None


async def test_no_exact_code_match_returns_none():
    items = [{"code": "AFL", "name": "애플락", "typeCode": "NYSE", "nationCode": "USA"}]
    async with _client(items) as client:
        assert await naver_search.find_overseas_korean_name("AAPL", client=client) is None


async def test_non_200_raises_for_retry():
    # non-200 은 결과 확정 불가(일시 실패) → 예외 전파. 호출자가 checked 박제 없이 재시도한다.
    async with _client(_AAPL_ITEMS, status=500) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await naver_search.find_overseas_korean_name("AAPL", client=client)


async def test_empty_items_returns_none():
    async with _client([]) as client:
        assert await naver_search.find_overseas_korean_name("AAPL", client=client) is None


async def test_blank_ticker_returns_none():
    async with _client(_AAPL_ITEMS) as client:
        assert await naver_search.find_overseas_korean_name("  ", client=client) is None
