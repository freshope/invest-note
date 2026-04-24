from datetime import datetime
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")
KST = _KST
MS_PER_DAY = 1000 * 60 * 60 * 24


def to_kst(utc_dt: datetime) -> datetime:
    """UTC datetime → KST datetime (Asia/Seoul)."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    return utc_dt.astimezone(_KST)
