"""asyncpg Connection 인터페이스를 흉내 내는 fake (테스트 전용)."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any


class FakeConnection:
    """응답을 순서대로 반환하는 fake asyncpg connection.

    각 fetch/fetchrow/fetchval/execute 호출마다 responses에서 순서대로 반환.
    SET LOCAL / set_config 호출은 no-op (responses 소비 안 함).
    """

    def __init__(self, *responses: Any) -> None:
        self._responses = list(responses)
        self._idx = 0

    def _next(self) -> Any:
        if self._idx >= len(self._responses):
            return None
        val = self._responses[self._idx]
        self._idx += 1
        return val

    def _is_internal(self, query: str) -> bool:
        q = query.strip().upper()
        return (
            q.startswith("SET LOCAL")
            or "SET_CONFIG" in q
            or "PG_ADVISORY_XACT_LOCK" in q
        )

    async def execute(self, query: str, *args: Any) -> str:
        if self._is_internal(query):
            return "OK"
        result = self._next()
        return result if isinstance(result, str) else "OK"

    async def executemany(self, query: str, args: Any) -> None:
        pass  # no-op — PnL 동기화 테스트에서 실제 UPDATE 불필요

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        result = self._next()
        return result if result is not None else []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return self._next()

    async def fetchval(self, query: str, *args: Any) -> Any:
        return self._next()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[None, None]:
        yield


def make_fake_acquire(conn: FakeConnection):
    """acquire_for_user 대체용 context manager 팩토리."""

    @asynccontextmanager
    async def _fake(pool: Any, user_id: Any) -> AsyncGenerator[FakeConnection, None]:
        yield conn

    return _fake
