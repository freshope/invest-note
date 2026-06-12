"""Naver 자동완성 기반 한국 종목 검색."""
from __future__ import annotations

import logging
import re
from typing import TypedDict

import httpx

from invest_note_api.domain.trade_types import DEFAULT_COUNTRY, MAX_CODE_LEN, MAX_NAME_LEN
from invest_note_api.external.constants import HTTP_TIMEOUT_SECONDS, NAVER_SEARCH_URL, USER_AGENT

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": USER_AGENT}
_CODE_RE = re.compile(r"^[A-Z0-9]{4,9}$", re.IGNORECASE)
_MIN_QUERY_LEN = 2
_MAX_RESULTS = 10

# Naver 자동완성 typeCode 중 한국 거래소만 채택. 미확인 typeCode는 보수적으로 거부 —
# 누락된 한국 거래소가 있어 매칭 실패가 보고되면 이 셋에 추가한다.
_KR_TYPE_CODES = frozenset({"KOSPI", "KOSDAQ", "KONEX", "ETF", "ETN", "ELW"})

# 미국 거래소 typeCode. US 종목 한글명 백필 전용(find_overseas_korean_name).
_US_TYPE_CODES = frozenset({"NASDAQ", "NYSE", "AMEX"})
_HANGUL_RE = re.compile(r"[가-힣]")


class StockSearchResult(TypedDict):
    code: str
    name: str
    market: str
    exchange: str


async def search_kr(
    q: str, *, client: httpx.AsyncClient | None = None
) -> list[StockSearchResult]:
    """Naver 자동완성으로 한국 종목 검색.

    HTTP 실패/빈 결과/예외는 모두 빈 리스트로 흡수한다 — 호출자가 try/except를 둘 필요 없다.
    `client` 를 주입하면 connection pool을 재사용한다 (대량 병렬 호출 시 권장).
    """
    try:
        if client is None:
            async with httpx.AsyncClient() as owned:
                res = await _do_get(owned, q)
        else:
            res = await _do_get(client, q)

        if res.status_code != 200:
            return []

        data = res.json()
        items = data.get("items") or []
        if not isinstance(items, list):
            return []

        results: list[StockSearchResult] = []
        for item in items[:_MAX_RESULTS]:
            code = item.get("code", "")
            name = item.get("name", "")
            type_code = item.get("typeCode", "")
            if not isinstance(code, str) or not isinstance(name, str):
                continue
            if not _CODE_RE.match(code):
                continue
            if type_code not in _KR_TYPE_CODES:
                continue
            results.append({
                "code": code[:MAX_CODE_LEN],
                "name": name[:MAX_NAME_LEN],
                "market": DEFAULT_COUNTRY,
                "exchange": type_code,
            })
        return results
    except httpx.HTTPError as e:
        # 타임아웃·연결 실패 등 일시적 네트워크 예외 — 대량 교차검증 중 흔하며 다음 run 재시도된다.
        # 트레이스백 없이 한 줄만 남겨 콘솔 노이즈를 줄인다.
        logger.info("naver_search 네트워크 예외 q=%r: %s", q, type(e).__name__)
        return []
    except Exception:
        logger.warning("naver_search 실패 q=%r", q, exc_info=True)
        return []


async def find_overseas_korean_name(
    ticker: str, *, client: httpx.AsyncClient | None = None
) -> str | None:
    """US 종목 ticker 의 Naver 한글명 1건 조회 — 별칭 백필 전용.

    Naver 자동완성에 ticker 를 질의하고 `code` 가 ticker 와 정확히 일치하는 미국 거래소
    항목의 한글명을 돌려준다. 한글이 없는 응답(영문 echo 등)은 별칭 가치가 없어 None.
    `search_kr` 과 분리한 이유: search_kr 은 한국 거래소 typeCode 만 채택하므로 US 를 거른다.

    HTTP 실패/빈 결과/예외는 모두 None 으로 흡수한다 — 대량 병렬 백필에서 호출자가
    try/except 를 둘 필요 없다.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return None
    try:
        if client is None:
            async with httpx.AsyncClient() as owned:
                res = await _do_get(owned, ticker)
        else:
            res = await _do_get(client, ticker)

        if res.status_code != 200:
            return None

        items = res.json().get("items") or []
        if not isinstance(items, list):
            return None

        for item in items:
            code = item.get("code", "")
            name = item.get("name", "")
            if not isinstance(code, str) or not isinstance(name, str):
                continue
            if code.upper() != ticker:
                continue
            if item.get("typeCode") not in _US_TYPE_CODES:
                continue
            if not _HANGUL_RE.search(name):
                return None  # 영문 echo — 별칭으로 둘 가치 없음
            return name[:MAX_NAME_LEN]
        return None
    except httpx.HTTPError as e:
        logger.info("naver overseas 네트워크 예외 ticker=%r: %s", ticker, type(e).__name__)
        return None
    except Exception:
        logger.warning("naver overseas 실패 ticker=%r", ticker, exc_info=True)
        return None


async def _do_get(client: httpx.AsyncClient, q: str) -> httpx.Response:
    return await client.get(
        NAVER_SEARCH_URL,
        params={"q": q, "target": "stock"},
        headers=_HEADERS,
        timeout=HTTP_TIMEOUT_SECONDS,
    )


async def find_first_kr_match(
    q: str, *, client: httpx.AsyncClient | None = None
) -> StockSearchResult | None:
    """입력 종목명으로 한국 종목 1건을 매칭한다.

    선택 우선순위:
    1. name이 입력과 정확일치하는 결과
    2. 첫 결과 (Naver 자동완성 1순위)

    입력 길이 < 2이면 None — "삼" 같은 1글자 입력의 자동 매칭으로 인한 오등록 방지.
    입력 길이 > MAX_NAME_LEN 이면 None — 비정상 종목명에 대한 외부 호출 가드.
    """
    q = q.strip()
    if len(q) < _MIN_QUERY_LEN or len(q) > MAX_NAME_LEN:
        return None

    results = await search_kr(q, client=client)
    if not results:
        return None

    for r in results:
        if r["name"] == q:
            return r

    return results[0]
