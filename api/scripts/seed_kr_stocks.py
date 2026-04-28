"""KRX 상장 종목을 kr_stocks 테이블에 적재한다.

사용법:
    cd api
    poetry run python scripts/seed_kr_stocks.py

KRX 정보데이터시스템 (data.krx.co.kr) 의 OTP 엔드포인트를 사용한다.
KOSPI / KOSDAQ / KONEX 순서로 조회하며 idempotent UPSERT 로 동작한다.
"""

import asyncio
import urllib.parse
import urllib.request
import json
import asyncpg
import os

from invest_note_api.config import Settings

_KRX_OTP_URL = "https://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
_KRX_DOWNLOAD_URL = "https://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"
_USER_AGENT = "Mozilla/5.0 (compatible; invest-note-seed/1.0)"

_MARKETS = {
    "KOSPI": "STK",
    "KOSDAQ": "KSQ",
    "KONEX": "KNX",
}


def _fetch_listing(market_code: str) -> list[dict]:
    """KRX에서 시장별 종목 목록을 CSV로 받아 파싱한다."""
    otp_params = {
        "locale": "ko_KR",
        "mktId": market_code,
        "trdDd": "",
        "money": "1",
        "csvxls_isNo": "false",
        "name": "fileDown",
        "url": "dbms/MDC/STAT/standard/MDCSTAT01901",
    }
    req = urllib.request.Request(
        _KRX_OTP_URL,
        data=urllib.parse.urlencode(otp_params).encode(),
        headers={"User-Agent": _USER_AGENT, "Referer": "https://data.krx.co.kr"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        otp = resp.read().decode("utf-8").strip()

    dl_req = urllib.request.Request(
        _KRX_DOWNLOAD_URL,
        data=urllib.parse.urlencode({"code": otp}).encode(),
        headers={"User-Agent": _USER_AGENT, "Referer": "https://data.krx.co.kr"},
    )
    with urllib.request.urlopen(dl_req, timeout=30) as resp:
        raw = resp.read().decode("euc-kr", errors="replace")

    lines = raw.strip().splitlines()
    if len(lines) < 2:
        return []

    header = [h.strip() for h in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        cols = [c.strip() for c in line.split(",")]
        rows.append(dict(zip(header, cols)))
    return rows


def _parse_rows(rows: list[dict], market: str) -> list[tuple[str, str, str]]:
    """(ticker, asset_name, market) 튜플 목록을 반환한다."""
    result = []
    for row in rows:
        ticker = (row.get("단축코드") or row.get("표준코드") or "").strip()
        name = (row.get("한글 종목명") or row.get("한글종목명") or "").strip()
        if ticker and name:
            result.append((ticker, name, market))
    return result


async def seed(db_url: str) -> None:
    conn = await asyncpg.connect(db_url)
    try:
        total = 0
        for market, code in _MARKETS.items():
            print(f"  [{market}] 조회 중...")
            try:
                rows = _fetch_listing(code)
                tuples = _parse_rows(rows, market)
                if not tuples:
                    print(f"  [{market}] 결과 없음 — 건너뜀")
                    continue
                await conn.executemany(
                    """
                    insert into public.kr_stocks (ticker, asset_name, market, updated_at)
                    values ($1, $2, $3, now())
                    on conflict (ticker) do update
                        set asset_name = excluded.asset_name,
                            market     = excluded.market,
                            updated_at = now()
                    """,
                    tuples,
                )
                print(f"  [{market}] {len(tuples)}건 upsert")
                total += len(tuples)
            except Exception as e:
                print(f"  [{market}] 오류: {e}")
        print(f"\n완료: 총 {total}건 upsert")
    finally:
        await conn.close()


if __name__ == "__main__":
    settings = Settings()
    # asyncpg expects postgresql:// scheme
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    asyncio.run(seed(db_url))
