"""공유 httpx.AsyncClient — FastAPI lifespan 에서 단일 인스턴스 관리.

라우터는 `Depends(get_http_client)` 로 주입받아 외부 호출 함수에 전달한다.
**callsite 가 `aclose()` 를 호출하지 않는다** — lifespan 책임.
"""
from __future__ import annotations

import httpx
from fastapi import Request

from invest_note_api.external.constants import HTTP_TIMEOUT_SECONDS


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client
