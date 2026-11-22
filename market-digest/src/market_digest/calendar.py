"""Per-exchange session calendars. All logic takes an explicit ``at_utc`` (no ``now()``)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Protocol

import exchange_calendars as xcals
import pandas as pd


class DayStatus(StrEnum):
    TRADING = "sesja"
    WEEKEND = "weekend"
    HOLIDAY = "święto / brak sesji"


class SessionCalendar(Protocol):
    def last_completed_session(self, exchange: str, at_utc: datetime) -> date | None: ...

    def day_status(self, exchange: str, local_day: date) -> DayStatus: ...


@lru_cache(maxsize=16)
def _cal(exchange: str) -> xcals.ExchangeCalendar:
    return xcals.get_calendar(exchange)


class ExchangeCalendars:
    """Adapter over ``exchange_calendars`` (handles holidays, early closes and DST)."""

    def last_completed_session(self, exchange: str, at_utc: datetime) -> date | None:
        if at_utc.tzinfo is None:
            raise ValueError("at_utc musi mieć strefę czasową")
        cal = _cal(exchange)
        ts = pd.Timestamp(at_utc).tz_convert("UTC")
        start = (ts - pd.Timedelta(days=15)).normalize().tz_localize(None)
        end = ts.normalize().tz_localize(None)
        sessions = cal.sessions_in_range(max(start, cal.first_session), min(end, cal.last_session))
        for session in reversed(list(sessions)):
            if cal.session_close(session) <= ts:
                return session.date()  # type: ignore[no-any-return]
        return None

    def day_status(self, exchange: str, local_day: date) -> DayStatus:
        cal = _cal(exchange)
        if cal.is_session(pd.Timestamp(local_day)):
            return DayStatus.TRADING
        if local_day.weekday() >= 5:
            return DayStatus.WEEKEND
        return DayStatus.HOLIDAY


def local_date(at_utc: datetime, tz: str) -> date:
    from zoneinfo import ZoneInfo

    return at_utc.astimezone(ZoneInfo(tz)).date()


def previous_days(d: date, n: int) -> list[date]:
    return [d - timedelta(days=i) for i in range(n)]
