"""daily_prices_repo 단위 테스트 — 쿼리 파라미터/매핑 (SQL 자체는 DB 적용 후 통합 검증).

AsyncMock conn 으로 호출 인자·반환 매핑만 검증한다 → 마이그레이션 미적용 상태에서도 통과.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

from invest_note_api.db_ops import daily_prices_repo


async def test_get_watermarks_empty_skips_db():
    conn = AsyncMock()
    assert await daily_prices_repo.get_watermarks(conn, []) == {}
    conn.fetch.assert_not_called()


async def test_get_watermarks_maps_ticker_to_max_date():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {"ticker": "005930", "max_date": date(2025, 6, 3)},
        {"ticker": "000660", "max_date": date(2025, 6, 2)},
    ]
    out = await daily_prices_repo.get_watermarks(conn, ["005930", "000660"])
    assert out == {"005930": date(2025, 6, 3), "000660": date(2025, 6, 2)}
    # 쿼리 인자: country_code, tickers.
    args = conn.fetch.call_args.args
    assert args[1] == "KR"
    assert args[2] == ["005930", "000660"]


async def test_get_closes_casts_numeric_to_float():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {"ticker": "005930", "close_date": date(2025, 6, 2), "close_price": Decimal("75000.00")},
    ]
    out = await daily_prices_repo.get_closes(
        conn, ["005930"], date(2025, 6, 1), date(2025, 6, 3)
    )
    assert out == [{"ticker": "005930", "close_date": date(2025, 6, 2), "close_price": 75000.0}]
    assert isinstance(out[0]["close_price"], float)
    args = conn.fetch.call_args.args
    assert args[3] == date(2025, 6, 1)  # begin
    assert args[4] == date(2025, 6, 3)  # end


async def test_get_closes_empty_skips_db():
    conn = AsyncMock()
    assert await daily_prices_repo.get_closes(conn, [], date(2025, 6, 1), date(2025, 6, 3)) == []
    conn.fetch.assert_not_called()


async def test_upsert_closes_filters_incomplete_rows():
    conn = AsyncMock()
    rows = [
        {"ticker": "005930", "close_date": date(2025, 6, 2), "close_price": 75000.0},
        {"ticker": "", "close_date": date(2025, 6, 2), "close_price": 75000.0},  # ticker 결측 제외.
        {"ticker": "000660", "close_date": None, "close_price": 100.0},  # date 결측 제외.
    ]
    n = await daily_prices_repo.upsert_closes(conn, rows)
    assert n == 1
    conn.executemany.assert_called_once()
    tuples = conn.executemany.call_args.args[1]
    assert tuples == [("KR", "005930", date(2025, 6, 2), 75000.0)]


async def test_upsert_closes_empty_skips_db():
    conn = AsyncMock()
    assert await daily_prices_repo.upsert_closes(conn, []) == 0
    conn.executemany.assert_not_called()


async def test_prune_older_than_parses_delete_count():
    conn = AsyncMock()
    conn.execute.return_value = "DELETE 42"
    n = await daily_prices_repo.prune_older_than(conn, date(2023, 6, 4))
    assert n == 42
    args = conn.execute.call_args.args
    assert args[2] == date(2023, 6, 4)
