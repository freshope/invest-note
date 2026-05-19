"""투자노트 데모 데이터 시드 — App Store 스크린샷용.

데모 계정에 계좌 3개 + 한국 주식 12종목에 걸친 BUY/SELL 거래 약 25건을 채운다.
이익/손실/부분매도/보유 시나리오가 섞여 분석 탭이 의미있게 보이도록 설계.

전제:
- BE 가상환경에서 실행 (`cd be && poetry run python scripts/seed_demo_data.py ...`)
- DATABASE_URL 이 .env.local 또는 환경변수로 설정되어 있고 service role 권한
- 데모 계좌는 이름 prefix "[데모]" 로 표시 — `--reset` 시 이 prefix 만 일괄 삭제

사용:
    # 이메일로 시드 (auth.users 조회)
    poetry run python scripts/seed_demo_data.py --email demo@example.com

    # user_id 직접 지정
    poetry run python scripts/seed_demo_data.py --user-id 00000000-0000-0000-0000-000000000000

    # 기존 데모 데이터 초기화 후 재시드
    poetry run python scripts/seed_demo_data.py --email demo@example.com --reset
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

# scripts/ 는 src 밖이라 sys.path 보정 (PYTHONPATH 설정 없이 동작하도록)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import asyncpg  # noqa: E402

from invest_note_api.config import get_settings  # noqa: E402
from invest_note_api.db import acquire_for_user, create_pool  # noqa: E402
from invest_note_api.db_ops.pnl_sync import recalc_group_pnl  # noqa: E402
from invest_note_api.db_ops.trades_repo import (  # noqa: E402
    insert_trade,
    list_trades_in_group,
)
from invest_note_api.domain.realized_pnl import TradeGroupKey  # noqa: E402
from invest_note_api.domain.trade_utils import KST  # noqa: E402

# ── 시드 설정 ────────────────────────────────────────────────────────────────

DEMO_NAME_PREFIX = "[데모]"

DEMO_ACCOUNTS = [
    {"name": f"{DEMO_NAME_PREFIX} 키움 위탁계좌", "broker": "키움증권", "cash_balance": Decimal("1500000")},
    {"name": f"{DEMO_NAME_PREFIX} 삼성 연금저축", "broker": "삼성증권", "cash_balance": Decimal("820000")},
    {"name": f"{DEMO_NAME_PREFIX} 토스 종합매매", "broker": "토스증권", "cash_balance": Decimal("2350000")},
]

# (ticker, 종목명, 기준가) — 2026 초 한국 시장 대략값
STOCKS = {
    "005930": ("삼성전자", 78_000),
    "000660": ("SK하이닉스", 195_000),
    "035420": ("NAVER", 210_000),
    "035720": ("카카오", 47_000),
    "068270": ("셀트리온", 178_000),
    "373220": ("LG에너지솔루션", 410_000),
    "005380": ("현대차", 285_000),
    "005490": ("POSCO홀딩스", 355_000),
    "055550": ("신한지주", 53_000),
    "105560": ("KB금융", 76_000),
    "006400": ("삼성SDI", 285_000),
    "011200": ("HMM", 17_200),
}

# 시나리오: (ticker, 계좌 인덱스, [(d_ago, type, price_mul, qty), ...])
# d_ago = 며칠 전, price_mul = 기준가에 곱할 배수
SCENARIOS: list[tuple[str, int, list[tuple[int, str, float, int]]]] = [
    # 보유 중 (분할 매수) — 미실현 손익이 분석 탭에 보임
    ("005930", 0, [(62, "BUY", 0.94, 30), (38, "BUY", 0.98, 20)]),
    ("000660", 0, [(50, "BUY", 0.92, 10), (15, "BUY", 1.02, 5)]),
    ("373220", 1, [(44, "BUY", 0.88, 5)]),

    # 전량 청산 + 이익 (SUCCESS)
    ("035420", 0, [(72, "BUY", 0.95, 15), (24, "SELL", 1.11, 15)]),
    ("005490", 1, [(80, "BUY", 0.90, 8), (32, "SELL", 1.09, 8)]),
    ("055550", 2, [(65, "BUY", 0.93, 50), (18, "SELL", 1.07, 50)]),
    ("006400", 2, [(58, "BUY", 0.88, 6), (22, "SELL", 1.05, 6)]),

    # 전량 청산 + 손실 (FAIL)
    ("035720", 0, [(55, "BUY", 1.05, 40), (28, "SELL", 0.92, 40)]),
    ("068270", 1, [(46, "BUY", 1.08, 8), (12, "SELL", 0.94, 8)]),
    ("011200", 2, [(40, "BUY", 1.10, 100), (33, "SELL", 0.93, 100)]),

    # 부분 매도 (이익 일부 + 잔량 보유)
    ("005380", 0, [(75, "BUY", 0.90, 10), (36, "BUY", 0.95, 5), (10, "SELL", 1.08, 7)]),
    ("105560", 2, [(52, "BUY", 0.92, 30), (14, "SELL", 1.06, 15)]),
]

STRATEGY_POOL = ["SCALPING", "SWING", "LONG_TERM"]
EMOTION_POOL = ["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]
TAG_POOL = ["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"]

BUY_REASONS = [
    "실적 가이던스 상향, 차트 반등 신호 포착",
    "신고가 돌파 후 눌림목 매수 진입",
    "외국인 5거래일 연속 순매수 + RSI 과매도 탈출",
    "분기 실적 컨센서스 상회 기대",
    "주요 거래선 수주 뉴스 모멘텀",
    "이격도 회복 + 거래량 동반 상승",
    "배당 기준일 전 분할 매수",
    "산업 사이클 저점 통과 판단",
    "테마 순환 진입",
    "장기 보유 목적 — 비중 확대",
]
SELL_REASONS = [
    "목표가 도달 — 익절",
    "1차 저항선 도달, 분할 매도",
    "손절가 터치 — 시스템 매도",
    "단기 과열 신호, 일부 차익실현",
    "실적 발표 후 모멘텀 둔화",
    "포트폴리오 리밸런싱",
    "추세선 이탈 — 보수적 청산",
    "다른 후보 종목 진입 위해 자금 확보",
]


def _pick_strategy(d_ago: int) -> str:
    """보유기간이 길수록 LONG_TERM 확률 ↑."""
    if d_ago > 60:
        return random.choices(STRATEGY_POOL, weights=[5, 35, 60])[0]
    if d_ago > 25:
        return random.choices(STRATEGY_POOL, weights=[15, 65, 20])[0]
    return random.choices(STRATEGY_POOL, weights=[45, 45, 10])[0]


def _pick_tags() -> list[str]:
    n = random.choices([1, 2, 3], weights=[40, 50, 10])[0]
    return random.sample(TAG_POOL, n)


def _kst_dt(d_ago: int) -> datetime:
    """며칠 전 KST 9:30~14:30 사이 랜덤 시각을 UTC datetime으로."""
    now_kst = datetime.now(KST)
    base = (now_kst - timedelta(days=d_ago)).date()
    hour = random.randint(9, 14)
    minute = random.choice([0, 10, 15, 23, 35, 42, 50])
    return datetime.combine(base, time(hour, minute), tzinfo=KST).astimezone(timezone.utc)


def _build_trade_row(
    *,
    account_id: str,
    ticker: str,
    asset_name: str,
    trade_type: str,
    price: float,
    quantity: int,
    traded_at: datetime,
) -> dict:
    """trades_repo.insert_trade 가 받는 dict 형식."""
    row: dict = {
        "account_id": account_id,
        "asset_name": asset_name,
        "ticker_symbol": ticker,
        "market_type": "STOCK",
        "trade_type": trade_type,
        "price": float(price),
        "quantity": float(quantity),
        "traded_at": traded_at,
        "commission": round(price * quantity * 0.00015, 0),  # 0.015% 가정
        "tax": round(price * quantity * 0.0023, 0) if trade_type == "SELL" else 0,
        "country_code": "KR",
        "exchange": "KOSPI",
    }

    if trade_type == "BUY":
        d_ago = (datetime.now(timezone.utc) - traded_at).days
        row["strategy_type"] = _pick_strategy(d_ago)
        row["emotion"] = random.choices(
            EMOTION_POOL, weights=[30, 15, 15, 10, 30]
        )[0]
        row["reasoning_tags"] = _pick_tags()
        # 70% 확률로 buy_reason 채움 (빈 케이스도 일부)
        if random.random() < 0.7:
            row["buy_reason"] = random.choice(BUY_REASONS)
    else:
        if random.random() < 0.65:
            row["sell_reason"] = random.choice(SELL_REASONS)

    return row


# ── 시드 실행 ───────────────────────────────────────────────────────────────


async def _resolve_user_id(pool: asyncpg.Pool, email: str) -> UUID:
    """auth.users 에서 email → user_id 조회. BE DB 커넥션이 service role 권한 가정."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM auth.users WHERE lower(email) = lower($1)",
            email,
        )
    if row is None:
        raise SystemExit(f"❌ email '{email}' 사용자를 찾을 수 없습니다. 먼저 가입해주세요.")
    return row["id"]


async def _reset_demo(conn: asyncpg.Connection, user_id: UUID) -> tuple[int, int]:
    """이름이 '[데모]' 로 시작하는 계좌와 그 거래만 삭제. 실데이터는 건드리지 않는다."""
    deleted_trades = await conn.execute(
        """
        DELETE FROM trades
         WHERE user_id = $1
           AND account_id IN (
               SELECT id FROM accounts
                WHERE user_id = $1 AND name LIKE $2
           )
        """,
        user_id,
        f"{DEMO_NAME_PREFIX}%",
    )
    deleted_accounts = await conn.execute(
        "DELETE FROM accounts WHERE user_id = $1 AND name LIKE $2",
        user_id,
        f"{DEMO_NAME_PREFIX}%",
    )

    def _count(tag: str) -> int:
        parts = tag.split()
        return int(parts[-1]) if parts[-1].isdigit() else 0

    return _count(deleted_trades), _count(deleted_accounts)


async def _seed_accounts(conn: asyncpg.Connection, user_id: UUID) -> list[str]:
    """데모 계좌 3개 생성. 반환: account_id 리스트 (DEMO_ACCOUNTS 와 동일 순서)."""
    ids: list[str] = []
    for acc in DEMO_ACCOUNTS:
        row = await conn.fetchrow(
            """
            INSERT INTO accounts (user_id, name, broker, cash_balance)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            user_id,
            acc["name"],
            acc["broker"],
            acc["cash_balance"],
        )
        ids.append(str(row["id"]))
    return ids


async def _seed_trades(
    conn: asyncpg.Connection, user_id: UUID, account_ids: list[str]
) -> tuple[int, int]:
    """시나리오별 거래 insert + 그룹 PnL 재계산. 반환: (buy_count, sell_count)."""
    buy_count = 0
    sell_count = 0

    for ticker, account_idx, legs in SCENARIOS:
        asset_name, base_price = STOCKS[ticker]
        account_id = account_ids[account_idx]
        group_key = TradeGroupKey(
            ticker=ticker, asset_name=asset_name, country="KR", account_id=account_id
        )

        # 시간 순(과거 → 현재)으로 정렬
        legs_sorted = sorted(legs, key=lambda x: -x[0])

        for d_ago, trade_type, mul, qty in legs_sorted:
            price = round(base_price * mul, 0)
            traded_at = _kst_dt(d_ago)
            row = _build_trade_row(
                account_id=account_id,
                ticker=ticker,
                asset_name=asset_name,
                trade_type=trade_type,
                price=price,
                quantity=qty,
                traded_at=traded_at,
            )
            await insert_trade(conn, str(user_id), row)
            if trade_type == "BUY":
                buy_count += 1
            else:
                sell_count += 1

        # 그룹 PnL 재계산 — SELL 행의 profit_loss/avg_buy_price/holding_days/result 자동 채움
        group_trades = await list_trades_in_group(conn, user_id, group_key)
        await recalc_group_pnl(conn, group_trades, group_key)

    return buy_count, sell_count


async def main_async(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("❌ DATABASE_URL 이 설정되지 않았습니다. be/.env.local 을 확인하세요.")

    pool = await create_pool(settings.database_url)
    try:
        if args.user_id:
            user_id = UUID(args.user_id)
        else:
            user_id = await _resolve_user_id(pool, args.email)

        print(f"▶ 데모 시드 대상 user_id = {user_id}")

        async with acquire_for_user(pool, user_id) as conn:
            if args.reset:
                t, a = await _reset_demo(conn, user_id)
                print(f"  ⤷ reset: trades {t}건, accounts {a}건 삭제")

            account_ids = await _seed_accounts(conn, user_id)
            print(f"  ⤷ 계좌 {len(account_ids)}개 생성")

            buys, sells = await _seed_trades(conn, user_id, account_ids)
            print(f"  ⤷ 거래 BUY {buys}건 / SELL {sells}건 생성 + PnL 자동 계산")

        print("✅ 시드 완료. 앱을 다시 로드하면 데이터가 보입니다.")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="투자노트 데모 데이터 시드")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user-id", help="auth.users.id (UUID)")
    group.add_argument("--email", help="auth.users.email — DB 에서 조회해 user_id 결정")
    parser.add_argument("--reset", action="store_true", help="기존 [데모] 계좌/거래 삭제 후 재시드")
    parser.add_argument("--seed", type=int, default=42, help="난수 시드 (재현성)")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
