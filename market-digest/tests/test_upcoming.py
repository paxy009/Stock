from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from market_digest import pipeline
from market_digest.config import UpcomingConfig
from market_digest.storage import Storage
from market_digest.upcoming import (
    closures,
    earnings_events,
    parse_earnings_calendar,
    parse_ecb,
    parse_fomc,
    within,
)
from tests.conftest import FakeCalendar, make_config

FOMC_HTML = """
<h4><a id="1">2026 FOMC Meetings</a></h4></div>
<div class="row fomc-meeting"><div class="fomc-meeting__month col-xs-5"><strong>January</strong></div>
<div class="fomc-meeting__date col-xs-4">27-28</div></div>
<div class="row fomc-meeting"><div class="fomc-meeting__month col-xs-5"><strong>December</strong></div>
<div class="fomc-meeting__date col-xs-4">8-9*</div></div>
<h4><a id="2">2027 FOMC Meetings</a></h4></div>
<div class="row fomc-meeting"><div class="fomc-meeting__month"><strong>Jan/Feb</strong></div>
<div class="fomc-meeting__date">31-1</div></div>
"""

ECB_HTML = """
<dl> <dt> 25/11/2026 </dt> <dd> Governing Council of the ECB: non-monetary policy meeting (in Frankfurt)<br> </dd>
<dt> 16/12/2026 </dt> <dd> Governing Council of the ECB: monetary policy meeting in Frankfurt (Day 1)<br> </dd>
<dt> 17/12/2026 </dt> <dd> Governing Council of the ECB: monetary policy meeting in Frankfurt (Day 2), followed by press conference<br> </dd>
<dt> 26/11/2026 </dt> <dd> General Council meeting of the ECB in Frankfurt<br> </dd></dl>
"""


def test_parse_fomc_uses_last_meeting_day_and_year_blocks() -> None:
    evs = parse_fomc(FOMC_HTML)
    assert [e.day for e in evs] == [date(2026, 1, 28), date(2026, 12, 9), date(2027, 2, 1)]
    assert "SEP" in evs[1].title and evs[0].certainty == "official"


def test_parse_ecb_keeps_only_decision_day() -> None:
    evs = parse_ecb(ECB_HTML)
    assert [e.day for e in evs] == [date(2026, 12, 17)]


def test_earnings_calendar_parsing_and_window() -> None:
    assert parse_earnings_calendar({"Earnings Date": [date(2026, 11, 25)]}) == [date(2026, 11, 25)]
    assert parse_earnings_calendar({"Earnings Date": ["2026-11-25", "2026-11-27"]}) == [
        date(2026, 11, 25), date(2026, 11, 27)]
    assert parse_earnings_calendar({}) == []
    assert parse_earnings_calendar(None) == []
    ev = earnings_events("NVDA", "NVIDIA", "us", [date(2026, 11, 25), date(2026, 11, 27)])[0]
    assert ev.certainty == "estimated" and "okno" in ev.title


def test_closures_only_weekday_holidays() -> None:
    thanks = date(2026, 11, 26)
    cal = FakeCalendar({"XNYS": {thanks}})
    evs = closures(cal.is_session, date(2026, 11, 23), date(2026, 11, 30))
    assert [(e.day, e.region) for e in evs] == [(thanks, "us")]


def test_within_is_exclusive_of_today_and_dedups() -> None:
    a = parse_ecb(ECB_HTML)[0]
    assert within([a, a], date(2026, 12, 17), date(2026, 12, 24)) == []
    assert within([a, a], date(2026, 12, 16), date(2026, 12, 24)) == [a]


class FakeUpcoming:
    def __init__(self, broken: bool = False) -> None:
        self.broken = broken

    def fomc_page(self) -> str:
        return "<html>redesigned</html>" if self.broken else FOMC_HTML

    def ecb_page(self) -> str:
        return ECB_HTML

    def earnings_dates(self, symbol: str) -> list[date]:
        return [date(2026, 12, 10)] if symbol == "NVDA" else []


def test_report_sections_10_and_next_up(tmp_path: Path) -> None:
    from tests.test_pipeline import _news, _prices

    at = datetime(2026, 12, 6, 22, 30, tzinfo=UTC)  # Sunday -> weekly horizon
    cfg = make_config(tmp_path).model_copy(update={"upcoming": UpcomingConfig(enabled=True)})
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), at)
    assert pipeline.fetch_upcoming(cfg, st, FakeUpcoming(), at) == {}
    res = pipeline.generate(cfg, st, FakeCalendar(), at)
    md = res.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    s10 = md.split("## 10.")[1].split("## 11.")[0]
    assert "2026-12-09 (środa)** — Fed — decyzja FOMC (z projekcjami SEP)" in s10
    assert "NVDA (NVIDIA) — publikacja wyników *(data szacunkowa" in s10
    assert "EBC — decyzja" not in s10  # 17.12 is beyond the 7-day horizon
    assert "Na co zwrócić uwagę w kolejnym dniu sesyjnym:** 2026-12-09: Fed" in md


def test_broken_page_is_reported_not_silent(tmp_path: Path) -> None:
    cfg = make_config(tmp_path).model_copy(update={"upcoming": UpcomingConfig(enabled=True)})
    st = Storage(cfg.app.db_path)
    failed = pipeline.fetch_upcoming(cfg, st, FakeUpcoming(broken=True),
                                     datetime(2026, 12, 6, tzinfo=UTC))
    assert "kalendarz:fomc" in failed


def test_stale_cache_survives_outage(tmp_path: Path) -> None:
    cfg = make_config(tmp_path).model_copy(update={"upcoming": UpcomingConfig(enabled=True,
                                                                             refresh_hours=1)})
    st = Storage(cfg.app.db_path)
    t0 = datetime(2026, 12, 6, tzinfo=UTC)
    pipeline.fetch_upcoming(cfg, st, FakeUpcoming(), t0)
    pipeline.fetch_upcoming(cfg, st, FakeUpcoming(broken=True), t0 + timedelta(hours=5))
    evs = pipeline.build_upcoming(cfg, st, FakeCalendar(), date(2026, 12, 6))
    assert any("FOMC" in e.title for e in evs)
