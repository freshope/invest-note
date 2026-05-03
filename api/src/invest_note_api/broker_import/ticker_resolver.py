"""종목명 → ticker 변환 (Naver 검색 API)."""

from __future__ import annotations

import asyncio

import httpx

from invest_note_api.external.naver_search import find_first_kr_match


async def resolve_tickers(
    asset_names: set[str],
    ticker_hints: dict[str, str],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str | None]:
    """asset_name → ticker 매핑.

    우선순위:
    1. ticker_hints (파일에서 직접 추출한 코드)
    2. Naver 검색 API 1순위 매칭 (한국 종목)
    3. None (미해결)

    `client` 는 라우터의 `Depends(get_http_client)` 로 주입받은 공유 인스턴스를 권장.
    None 으로 호출하면 `find_first_kr_match` 가 매번 새 client 를 생성한다 (테스트 호환성용).
    """
    result: dict[str, str | None] = {}

    remaining: list[str] = []
    for name in asset_names:
        if name in ticker_hints:
            result[name] = ticker_hints[name]
        else:
            remaining.append(name)

    if remaining:
        matches = await asyncio.gather(
            *(find_first_kr_match(n, client=client) for n in remaining)
        )
        for name, match in zip(remaining, matches):
            result[name] = match["code"] if match else None

    return result
