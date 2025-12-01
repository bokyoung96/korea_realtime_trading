from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional


class TimeService:
    KST: timezone = timezone(timedelta(hours=9))

    @classmethod
    def now_kst(cls) -> datetime:
        return datetime.now(tz=cls.KST)

    @classmethod
    def now_kst_naive(cls) -> datetime:
        return cls.now_kst().replace(tzinfo=None)

    @classmethod
    def to_kst_naive(cls, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(cls.KST).replace(tzinfo=None)

    @classmethod
    def floor_minute_kst(cls, dt: Optional[datetime] = None) -> datetime:
        base = dt if dt is not None else datetime.now(tz=cls.KST)
        if base.tzinfo is None:
            base = base.replace(tzinfo=cls.KST)
        floored = base.replace(second=0, microsecond=0)
        return floored.replace(tzinfo=None)