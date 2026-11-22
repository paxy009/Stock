"""Real exchange calendars (exchange_calendars) for regional holidays and DST."""

from datetime import UTC, date, datetime

import pytest

from market_digest.calendar import DayStatus, ExchangeCalendars

cal = ExchangeCalendars()


def at(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(UTC)


def test_saturday_uses_friday_session() -> None:
    assert cal.last_completed_session("XNYS", at("2025-11-22T23:30+01:00")) == date(2025, 11, 21)
    assert cal.day_status("XNYS", date(2025, 11, 22)) == DayStatus.WEEKEND


def test_us_thanksgiving_while_tokyo_trades() -> None:
    now = at("2025-11-27T23:30+01:00")
    assert cal.last_completed_session("XNYS", now) == date(2025, 11, 26)
    assert cal.last_completed_session("XTKS", now) == date(2025, 11, 27)
    assert cal.day_status("XNYS", date(2025, 11, 27)) == DayStatus.HOLIDAY


def test_japan_golden_week_while_us_trades() -> None:
    now = at("2025-05-06T23:30+02:00")
    assert cal.last_completed_session("XNYS", now) == date(2025, 5, 6)
    assert cal.last_completed_session("XTKS", now) == date(2025, 5, 2)


def test_us_dst_shift_before_europe() -> None:
    # 9 March 2025: US already on DST (close 20:00 UTC), Europe still on CET.
    assert cal.last_completed_session("XNYS", at("2025-03-10T21:30+01:00")) == date(2025, 3, 10)
    # One week earlier (no DST anywhere) close is 21:00 UTC -> 20:30 UTC is before close.
    assert cal.last_completed_session("XNYS", at("2025-03-03T21:30+01:00")) == date(2025, 2, 28)


def test_requires_timezone() -> None:
    with pytest.raises(ValueError):
        cal.last_completed_session("XNYS", datetime(2025, 1, 2, 12))
