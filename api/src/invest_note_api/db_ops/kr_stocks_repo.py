from asyncpg import Connection


async def lookup_by_names(conn: Connection, names: list[str]) -> dict[str, str]:
    """종목명 목록을 받아 {asset_name: ticker} 매핑을 반환한다.

    동일 종목명이 여러 시장에 존재할 경우 KOSPI > KOSDAQ > KONEX 우선순위로 1건만 반환.
    """
    if not names:
        return {}

    rows = await conn.fetch(
        """
        select distinct on (asset_name) asset_name, ticker
        from public.kr_stocks
        where asset_name = any($1::text[])
        order by asset_name,
                 case market when 'KOSPI' then 0 when 'KOSDAQ' then 1 else 2 end
        """,
        names,
    )
    return {row["asset_name"]: row["ticker"] for row in rows}
