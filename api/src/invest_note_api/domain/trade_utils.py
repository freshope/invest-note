from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
KST_OFFSET = "+09:00"
MS_PER_DAY = 1000 * 60 * 60 * 24

_KST_MARKET_OPEN = time(9, 0)


def to_kst(utc_dt: datetime) -> datetime:
    """UTC datetime → KST datetime (Asia/Seoul)."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    return utc_dt.astimezone(KST)


def to_kst_ms(utc_dt: datetime) -> int:
    """UTC datetime → KST 기준 epoch milliseconds."""
    return int(to_kst(utc_dt).timestamp() * 1000)


def kst_date_to_utc(d: date, t: time = _KST_MARKET_OPEN) -> datetime:
    """KST 날짜 + 시간 → UTC datetime. 거래내역서처럼 시각이 없는 입력에 KST 장 시작(09:00)을 부여한다."""
    return datetime.combine(d, t, tzinfo=KST).astimezone(timezone.utc)


def position_key(ticker: str | None, country: str) -> str:
    """티커+국가 기반 포지션 dict 키 (account 미포함)."""
    return f"{ticker}:{country}"
