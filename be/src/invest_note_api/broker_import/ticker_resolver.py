"""종목명 → ticker 변환 (Naver 검색 API)."""

from __future__ import annotations

import asyncio
from typing import TypedDict

import httpx

from invest_note_api.external.naver_search import find_first_kr_match


class ResolvedTicker(TypedDict):
    code: str
    exchange: str


async def resolve_tickers(
    asset_names: set[str],
    ticker_hints: dict[str, str],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, ResolvedTicker | None]:
    """asset_name → {code, exchange} 매핑.

    - code: ticker_hints(파일에서 직접 추출한 코드)가 있으면 그것을 권위로 사용,
      없으면 Naver 검색 1순위 매칭.
    - exchange: 파일에는 거래소 정보가 없으므로 항상 Naver 매칭에서 가져온다.
      hint 가 있어 code 는 확정이어도 exchange 채움을 위해 Naver 를 조회한다.
    - 미해결(코드 없음): None.

    `client` 는 라우터의 `Depends(get_http_client)` 로 주입받은 공유 인스턴스를 권장.
    None 으로 호출하면 `find_first_kr_match` 가 매번 새 client 를 생성한다 (테스트 호환성용).
    """
    names = list(asset_names)
    matches = await asyncio.gather(
        *(find_first_kr_match(n, client=client) for n in names)
    )

    result: dict[str, ResolvedTicker | None] = {}
    for name, match in zip(names, matches):
        hint = ticker_hints.get(name)
        if hint is not None:
            result[name] = {
                "code": hint,
                "exchange": match["exchange"] if match else "",
            }
        elif match is not None:
            result[name] = {"code": match["code"], "exchange": match["exchange"]}
        else:
            result[name] = None

    return result
