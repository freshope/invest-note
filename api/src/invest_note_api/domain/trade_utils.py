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


def kst_date_to_utc(d: date, t: time = _KST_MARKET_OPEN) -> datetime:
    """KST 날짜 + 시간 → UTC datetime. 거래내역서처럼 시각이 없는 입력에 KST 장 시작(09:00)을 부여한다."""
    return datetime.combine(d, t, tzinfo=KST).astimezone(timezone.utc)
