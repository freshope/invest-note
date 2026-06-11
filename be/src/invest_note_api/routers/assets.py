"""assets 라우터 — 자산 변화(일별 평가액 추이). 계좌뷰/종목뷰 단일 엔드포인트.

흐름: 거래 로드 → (커넥션 밖에서) data.go.kr 종가 backfill → get_closes → 오늘 라이브 시세
→ asset_history 순수 계산 → 응답. data.go.kr fetch 는 느리므로(14~18초) 풀 커넥션을
잡고 있지 않도록 fetch 전후로 커넥션 획득을 분리한다(portfolio/admin 과 동일 정책).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops import daily_prices_repo
from invest_note_api.db_ops.trades_repo import list_trades_with_account
from invest_note_api.domain.asset_history import (
    compute_asset_history,
    market_open_today,
    scope_earliest_date,
    scope_tickers,
)
from invest_note_api.domain.portfolio import holding_invested_amount
from invest_note_api.domain.trade_types import (
    CURRENCY_KRW,
    COUNTRY_US,
    currency_for_country,
    to_krw,
    trade_country,
)
from invest_note_api.domain.trade_utils import KST, position_key
from invest_note_api.external.fx import (
    FxCacheState,
    get_fx_cache_state,
    usdkrw_if_foreign,
)
from invest_note_api.external.http_client import get_http_client
from invest_note_api.external.quotes import (
    QuoteCacheState,
    fetch_quotes_by_keys,
    get_quote_cache_state,
)
from invest_note_api.services import daily_price_seed
from invest_note_api.schemas.asset_response import AssetHistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assets")


@router.get("/history", response_model=AssetHistoryResponse)
async def get_asset_history(
    account_id: str | None = Query(default=None, alias="accountId"),
    ticker: str | None = Query(default=None),
    country: str = Query(default="KR"),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    settings: Settings = Depends(get_settings),
    quote_state: QuoteCacheState = Depends(get_quote_cache_state),
    fx_state: FxCacheState = Depends(get_fx_cache_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> AssetHistoryResponse:
    is_stock_view = bool(ticker)
    today = datetime.now(KST).date()

    # 1) 스코프 거래 로드. 종목뷰(ticker 지정)는 단일 종목이라 country push 유지.
    # 전체/계좌뷰(ticker=None)는 country 필터 제거 → US/KR 보유를 모두 로드하고 아래에서
    # country 별로 분리해 KRW 로 환산·합산한다(finding A: 대시보드 합계와 포함범위 일치).
    async with acquire_for_user(pool, user.id) as conn:
        trades = await list_trades_with_account(
            conn,
            user.id,
            account_id=account_id,
            ticker=ticker if is_stock_view else None,
            country=country if is_stock_view else None,
        )

    if not trades:
        return AssetHistoryResponse.model_validate(
            {"series": [], "items": [], "incomplete": False, "as_of": _now_iso()}
        )

    earliest = scope_earliest_date(trades, today)

    # 거래를 country(KR/US) 별로 분리 — backfill/get_closes 가 country 단위 스칼라 인자라
    # 그룹별로 호출해야 한다. 순회 순서를 고정(아래 dict 삽입순)해 결정적 동작.
    trades_by_country: dict[str, list] = {}
    for t in trades:
        trades_by_country.setdefault(trade_country(t), []).append(t)

    has_foreign = any(
        currency_for_country(c) != CURRENCY_KRW for c in trades_by_country
    )

    # 해외(비-KRW) 보유가 있을 때만 USD/KRW spot 1회 조회(None 가능 — 환율 미상).
    # FX 는 DB backfill/quotes 와 독립이라 create_task 로 동시 실행하고, 실제 사용 직전(아래
    # _invested_amount_krw / compute_asset_history)에 await 해 임계 경로 직렬 지연을 줄인다.
    fx_task = asyncio.create_task(
        usdkrw_if_foreign(
            trades, fx_state, http_client, providers=settings.fx_provider_list
        )
    )

    # 2) country 별 backfill + get_closes. get_closes 반환에는 country 차원이 없어,
    # merge 전에 각 행에 country 를 태깅해 compute 가 (ticker, country) 로 구분하게 한다(D1).
    incomplete_fetch = False
    closes: list[dict] = []
    async with acquire_for_user(pool, user.id) as conn:
        for country_code, country_trades in trades_by_country.items():
            tickers = scope_tickers(country_trades)
            if not tickers:
                continue
            # primary 공급자는 country 별로 선택 — US 는 US_DAILY_PRICE_PROVIDER(Yahoo),
            # 그 외는 DAILY_PRICE_PROVIDER. US 는 gap 개념이 없어 gap_provider 는 무시된다.
            grp_incomplete = await daily_price_seed.backfill_closes(
                conn,
                settings.data_go_kr_api_key,
                tickers,
                earliest,
                today,
                country_code=country_code,
                primary_provider=(
                    settings.us_daily_price_provider
                    if country_code == COUNTRY_US
                    else settings.daily_price_provider
                ),
                gap_provider=settings.daily_price_gap_provider,
            )
            incomplete_fetch = incomplete_fetch or grp_incomplete
            grp_closes = await daily_prices_repo.get_closes(
                conn, tickers, earliest, today, country_code=country_code
            )
            for c in grp_closes:
                closes.append({**c, "country": country_code})

    # 3) 오늘 점 라이브 시세 — position_key(ticker, country) → native price 맵.
    # fetch_quotes_by_keys 는 키의 country 로 KR/US 공급자를 내부 라우팅하므로 1회 호출.
    live_quotes: dict[str, float] = {}
    quotes: dict = {}
    all_keys = [
        position_key(tk, country_code)
        for country_code, country_trades in trades_by_country.items()
        for tk in scope_tickers(country_trades)
    ]
    if all_keys:
        try:
            quotes = await fetch_quotes_by_keys(
                quote_state,
                all_keys,
                client=http_client,
                providers=settings.quote_provider_list,
                us_providers=settings.us_quote_provider_list,
            )
        except Exception:
            logger.warning("asset_history 시세 조회 실패 user_id=%s", user.id, exc_info=True)
            quotes = {}
        for key, q in quotes.items():
            if q is not None:
                live_quotes[key] = q["price"]

    usdkrw = await fx_task

    # 현재 보유분 매수 원금(KRW) — 차트 손익 기준 가이드 라인. 혼재 스코프는 native 단일통화
    # 합산이 통화 무가산 버그라(D5), country 별 holding_invested_amount 를 spot 으로 KRW 환산.
    invested_amount = _invested_amount_krw(trades_by_country, usdkrw)

    # 4) 순수 계산 — 휴장일(시세 traded_on ≠ 오늘)이면 오늘 점 제외.
    result = compute_asset_history(
        trades,
        closes,
        live_quotes,
        today=today,
        is_stock_view=is_stock_view,
        include_today=market_open_today(list(quotes.values()), today),
        usdkrw=usdkrw,
    )

    return AssetHistoryResponse.model_validate(
        {
            "series": result.series,
            "items": result.items,
            "incomplete": result.incomplete or incomplete_fetch,
            "as_of": _now_iso(),
            "invested_amount": invested_amount,
            "usdkrw": usdkrw,
            "has_foreign": has_foreign,
        }
    )


def _invested_amount_krw(
    trades_by_country: dict[str, list], usdkrw: float | None
) -> float | None:
    """country 별 매수 원금(native)을 KRW 로 환산·합산(D5).

    KR 은 KRW 그대로, US 는 spot usdkrw 환산. usdkrw=None 이면 US 기여 제외(곡선과 일치).
    보유가 없으면(전 country None) None — FE 단색 차트 폴백.
    """
    total: float | None = None
    for country_code, country_trades in trades_by_country.items():
        native = holding_invested_amount(country_trades)
        if native is None:
            continue
        krw = to_krw(native, currency_for_country(country_code), usdkrw)
        if krw is None:
            continue  # USD + 환율 미상 → 기여 제외(곡선의 US 제외와 동일).
        total = (total or 0.0) + krw
    return total


def _now_iso() -> str:
    """마지막 점 기준시각 — KST ISO8601(+09:00). 오늘 점은 라이브 시세 시각."""
    return datetime.now(KST).isoformat()
