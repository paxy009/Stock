from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from market_digest.calendar import DayStatus
from market_digest.config import Config
from market_digest.models import NewsItem, PriceBar

DM = ["US", "CA", "DE", "FR", "GB", "NL", "CH", "SE", "JP", "AU", "HK", "SG", "NZ"]


def make_config(tmp_path: Path, instruments: list[dict[str, Any]] | None = None,
                **overrides: Any) -> Config:
    data: dict[str, Any] = {
        "app": {"db_path": str(tmp_path / "m.db"), "reports_dir": str(tmp_path / "reports")},
        "coverage": {"developed_countries": DM},
        "instruments": instruments if instruments is not None else default_instruments(),
        "fx_pairs": {"USD": "USDPLN=X"},
    }
    data.update(overrides)
    return Config.model_validate(data)


def default_instruments() -> list[dict[str, Any]]:
    return [
        {"symbol": "SPY", "name": "SPY", "kind": "etf", "region": "us", "currency": "USD",
         "exchange": "XNYS", "exposure_countries": ["US"]},
        {"symbol": "VGK", "name": "VGK", "kind": "etf", "region": "developed_europe",
         "currency": "USD", "exchange": "XNYS", "exposure_countries": ["DE", "FR", "GB"],
         "is_regional_proxy": True},
        {"symbol": "EWJ", "name": "EWJ", "kind": "etf", "region": "developed_asia",
         "currency": "USD", "exchange": "XNYS", "exposure_countries": ["JP"],
         "is_regional_proxy": True},
        {"symbol": "NVDA", "name": "NVIDIA", "kind": "equity", "region": "us", "currency": "USD",
         "exchange": "XNYS", "issuer_country": "US", "benchmark": "SPY"},
        {"symbol": "TSM", "name": "TSMC ADR", "kind": "equity", "region": "developed_asia",
         "currency": "USD", "exchange": "XNYS", "issuer_country": "TW"},
    ]


def sessions(end: date, n: int) -> list[date]:
    """n weekday sessions ending at ``end`` (inclusive)."""
    out: list[date] = []
    d = end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return sorted(out)


def bars_from(closes: list[float], end: date, adj: list[float] | None = None) -> list[PriceBar]:
    days = sessions(end, len(closes))
    adj = adj or closes
    return [PriceBar(d, c, a) for d, c, a in zip(days, closes, adj, strict=True)]


class FakeCalendar:
    """Weekday sessions closing at 21:00 UTC; optional holidays per exchange."""

    def __init__(self, holidays: dict[str, set[date]] | None = None) -> None:
        self.holidays = holidays or {}

    def _is_session(self, exchange: str, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays.get(exchange, set())

    def last_completed_session(self, exchange: str, at_utc: datetime) -> date | None:
        d = at_utc.date()
        if at_utc.astimezone(UTC).hour < 21:
            d -= timedelta(days=1)
        for _ in range(15):
            if self._is_session(exchange, d):
                return d
            d -= timedelta(days=1)
        return None

    def day_status(self, exchange: str, local_day: date) -> DayStatus:
        if self._is_session(exchange, local_day):
            return DayStatus.TRADING
        return DayStatus.WEEKEND if local_day.weekday() >= 5 else DayStatus.HOLIDAY


def news(title: str, url: str, published: datetime, feed: str = "fed",
         tier: str = "official", summary: str = "") -> NewsItem:
    from market_digest.providers.news import canonical_url

    return NewsItem(feed, feed.upper(), tier, title, url, canonical_url(url), published,
                    published, summary)


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return make_config(tmp_path)
