"""종목명 → ticker 변환 (Naver 검색 API)."""

from __future__ import annotations

import asyncio

import httpx

from invest_note_api.external.naver_search import find_first_kr_match


async def resolve_tickers(
    asset_names: set[str],
    ticker_hints: dict[str, str],
) -> dict[str, str | None]:
    """asset_name → ticker 매핑.

    우선순위:
    1. ticker_hints (파일에서 직접 추출한 코드)
    2. Naver 검색 API 1순위 매칭 (한국 종목)
    3. None (미해결)
    """
    result: dict[str, str | None] = {}

    remaining: list[str] = []
    for name in asset_names:
        if name in ticker_hints:
            result[name] = ticker_hints[name]
        else:
            remaining.append(name)

    if remaining:
        # 단일 client로 connection pool 재사용 — N개 종목 동시 검색 시 keepalive 활용
        async with httpx.AsyncClient() as client:
            matches = await asyncio.gather(
                *(find_first_kr_match(n, client=client) for n in remaining)
            )
        for name, match in zip(remaining, matches):
            result[name] = match["code"] if match else None

    return result
