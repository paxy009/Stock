"""Upcoming events (section 10): central bank meetings, earnings dates, exchange closures."""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"], start=1)}
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
ECB_URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"

_FOMC_YEAR = re.compile(r"(\d{4}) FOMC Meetings")
_FOMC_ROW = re.compile(
    r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<',
    re.S)
_ECB_ROW = re.compile(r"<dt>\s*(\d{2})/(\d{2})/(\d{4})\s*</dt>\s*<dd>(.*?)</dd>", re.S)


@dataclass(frozen=True, slots=True)
class UpcomingEvent:
    day: date
    title: str
    kind: str  # central_bank | earnings | market_closure
    region: str
    source_name: str
    source_url: str
    certainty: str  # official | estimated


def parse_fomc(page: str) -> list[UpcomingEvent]:
    """FOMC decision day = last day of the meeting (statement released then)."""
    out: list[UpcomingEvent] = []
    marks = list(_FOMC_YEAR.finditer(page))
    for i, m in enumerate(marks):
        year = int(m.group(1))
        chunk = page[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(page)]
        for month_txt, days_txt in _FOMC_ROW.findall(chunk):
            months = [MONTHS.get(x.strip().lower()) for x in month_txt.split("/")]
            nums = [int(x) for x in re.findall(r"\d+", days_txt)]
            if not nums or None in months:
                continue
            month = months[-1]
            assert month is not None
            try:
                day = date(year, month, nums[-1])
            except ValueError:
                continue
            note = " (z projekcjami SEP)" if "*" in days_txt else ""
            out.append(UpcomingEvent(day, f"Fed — decyzja FOMC{note}", "central_bank", "us",
                                     "Federal Reserve", FOMC_URL, "official"))
    return out


def parse_ecb(page: str) -> list[UpcomingEvent]:
    out: list[UpcomingEvent] = []
    for dd, mm, yyyy, desc in _ECB_ROW.findall(page):
        text = html_lib.unescape(re.sub(r"<[^>]+>", " ", desc)).strip().lower()
        # Decision is announced on the last day of a monetary policy meeting.
        if "monetary policy meeting" not in text or "non-monetary" in text:
            continue
        if "day 1" in text:
            continue
        try:
            day = date(int(yyyy), int(mm), int(dd))
        except ValueError:
            continue
        out.append(UpcomingEvent(day, "EBC — decyzja w sprawie stóp procentowych",
                                 "central_bank", "developed_europe", "ECB", ECB_URL, "official"))
    return out


def within(events: list[UpcomingEvent], start: date, end: date) -> list[UpcomingEvent]:
    """Events with start < day <= end, deduplicated, chronological."""
    seen: set[tuple[date, str]] = set()
    out: list[UpcomingEvent] = []
    for e in sorted(events, key=lambda x: (x.day, x.kind, x.title)):
        if start < e.day <= end and (e.day, e.title) not in seen:
            seen.add((e.day, e.title))
            out.append(e)
    return out


def parse_earnings_calendar(cal: object) -> list[date]:
    """Defensive parse of yfinance ``Ticker.calendar`` (dict with 'Earnings Date': [date, ...])."""
    if not isinstance(cal, dict):
        return []
    raw = cal.get("Earnings Date")
    if raw is None:
        return []
    items = raw if isinstance(raw, list | tuple) else [raw]
    out: list[date] = []
    for it in items:
        if isinstance(it, datetime):
            out.append(it.date())
        elif isinstance(it, date):
            out.append(it)
        elif isinstance(it, str):
            try:
                out.append(date.fromisoformat(it[:10]))
            except ValueError:
                continue
    return sorted(set(out))


def earnings_events(symbol: str, name: str, region: str, days: list[date]) -> list[UpcomingEvent]:
    if not days:
        return []
    # Yahoo can give a window (two dates) when the exact day is not confirmed.
    title = f"{symbol} ({name}) — publikacja wyników"
    if len(days) > 1:
        title += f" (okno {days[0].isoformat()}–{days[-1].isoformat()})"
    return [UpcomingEvent(days[0], title, "earnings", region, "Yahoo Finance",
                          f"https://finance.yahoo.com/quote/{symbol}", "estimated")]


EXCHANGE_NAMES = {"XNYS": ("NYSE/Nasdaq", "us"), "XETR": ("Xetra (Frankfurt)", "developed_europe"),
                  "XLON": ("LSE (Londyn)", "developed_europe"),
                  "XTKS": ("Tokio", "developed_asia"), "XTSE": ("Toronto", "other_developed"),
                  "XASX": ("Sydney (ASX)", "other_developed")}


def closures(is_session: Callable[[str, date], bool], start: date, end: date
             ) -> list[UpcomingEvent]:
    """Weekdays without a session (holidays) per monitored exchange."""
    out: list[UpcomingEvent] = []
    d = start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() >= 5:
            continue
        for code, (name, region) in EXCHANGE_NAMES.items():
            try:
                if not is_session(code, d):
                    out.append(UpcomingEvent(d, f"{name} — brak sesji (święto)", "market_closure",
                                             region, "exchange_calendars",
                                             "https://github.com/gerrymanoim/exchange_calendars",
                                             "official"))
            except Exception:
                continue
    return out
