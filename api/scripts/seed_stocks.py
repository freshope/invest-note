"""KRX 상장 종목을 stocks 테이블(country_code='KR')에 적재한다.

사용법:
    cd api
    poetry run python scripts/seed_stocks.py

KIND 상장공시시스템(kind.krx.co.kr) 의 corpList 엔드포인트를 사용한다.
KOSPI / KOSDAQ / KONEX 순서로 조회하며 idempotent UPSERT 로 동작한다.
"""

import asyncio
import datetime as _dt
import html as _html
import re
import sys
import urllib.request
from pathlib import Path

import asyncpg

# pyproject.toml 이 package-mode=false 라 invest_note_api 가 site-packages 에 없다.
# pytest 는 [tool.pytest.ini_options].pythonpath 로 해결되지만, 일반 python 호출에는
# 직접 src 경로를 sys.path 에 등록해야 한다.
_API_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from invest_note_api.config import Settings  # noqa: E402
from invest_note_api.external.constants import USER_AGENT  # noqa: E402

_KIND_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do"

# (논리 시장명, KIND query param)
_MARKETS = (
    ("KOSPI", "stockMkt"),
    ("KOSDAQ", "kosdaqMkt"),
    ("KONEX", "konexMkt"),
)

# KIND 시장구분 컬럼 값 → 표준화된 market 코드
_MARKET_LABEL_MAP = {
    "유가": "KOSPI",
    "코스닥": "KOSDAQ",
    "코넥스": "KONEX",
}


def _fetch_kind_html(market_param: str) -> str:
    """KIND 상장법인 목록을 EUC-KR 디코딩한 HTML 문자열로 반환한다."""
    url = f"{_KIND_URL}?method=download&searchType=13&marketType={market_param}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("euc-kr", errors="replace")


def _parse_kind_html(html: str, market: str) -> list[dict]:
    """KIND HTML 테이블을 파싱해 stocks UPSERT 입력 dict 리스트로 변환한다.

    KIND 컬럼 순서: 회사명, 시장구분, 종목코드, 업종, 주요제품, 상장일,
                   결산월, 대표자명, 홈페이지, 지역
    """
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    parsed: list[dict] = []
    for row in rows[1:]:  # 첫 행은 헤더
        cells_raw = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
        cells = [_html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells_raw]
        if len(cells) < 10:
            continue

        ticker = cells[2]
        asset_name = cells[0]
        if not ticker or not asset_name:
            continue

        normalized_market = _MARKET_LABEL_MAP.get(cells[1], market)
        parsed.append({
            "ticker": ticker,
            "asset_name": asset_name,
            "market": normalized_market,
            "sector": cells[3] or None,
            "main_products": cells[4] or None,
            "listed_at": _parse_date(cells[5]),
            "fiscal_month": cells[6] or None,
            "ceo_name": cells[7] or None,
            "homepage": cells[8] or None,
            "region": cells[9] or None,
        })
    return parsed


def _parse_date(value: str) -> _dt.date | None:
    """'YYYY-MM-DD' 형식을 date로. 빈 값 / 파싱 실패 시 None."""
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:
        return None


_UPSERT_SQL = """
insert into public.stocks (
    country_code, ticker, asset_name, market, currency, exchange,
    sector, main_products, listed_at, fiscal_month, ceo_name, homepage, region,
    updated_at
) values (
    'KR', $1, $2, $3, 'KRW', 'KRX',
    $4, $5, $6, $7, $8, $9, $10,
    now()
)
on conflict (country_code, ticker) do update set
    asset_name    = excluded.asset_name,
    market        = excluded.market,
    currency      = excluded.currency,
    exchange      = excluded.exchange,
    sector        = excluded.sector,
    main_products = excluded.main_products,
    listed_at     = excluded.listed_at,
    fiscal_month  = excluded.fiscal_month,
    ceo_name      = excluded.ceo_name,
    homepage      = excluded.homepage,
    region        = excluded.region,
    updated_at    = now()
"""


async def seed(db_url: str) -> None:
    conn = await asyncpg.connect(db_url)
    try:
        total = 0
        for market, param in _MARKETS:
            print(f"  [{market}] KIND 조회 중...")
            try:
                html = _fetch_kind_html(param)
                rows = _parse_kind_html(html, market)
                if not rows:
                    print(f"  [{market}] 결과 없음 — 건너뜀")
                    continue
                tuples = [
                    (
                        r["ticker"],
                        r["asset_name"],
                        r["market"],
                        r["sector"],
                        r["main_products"],
                        r["listed_at"],
                        r["fiscal_month"],
                        r["ceo_name"],
                        r["homepage"],
                        r["region"],
                    )
                    for r in rows
                ]
                await conn.executemany(_UPSERT_SQL, tuples)
                print(f"  [{market}] {len(tuples)}건 upsert")
                total += len(tuples)
            except Exception as e:
                print(f"  [{market}] 오류: {e}")
        print(f"\n완료: 총 {total}건 upsert")
    finally:
        await conn.close()


if __name__ == "__main__":
    settings = Settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    asyncio.run(seed(db_url))
