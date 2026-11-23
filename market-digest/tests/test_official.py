from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from market_digest.fundamentals import Fact, extract, latest_per_period
from market_digest.macro import MacroObs, summarize
from market_digest.providers.official import (
    parse_company_facts,
    parse_fred_csv,
    parse_recent_8k,
    parse_ticker_map,
)


def F(concept: str, start: str | None, end: str, val: float, filed: str = "2026-08-26",
      form: str = "10-Q", unit: str = "USD", accn: str = "a") -> Fact:
    return Fact(concept, unit, date.fromisoformat(start) if start else None,
                date.fromisoformat(end), val, None, None, form, date.fromisoformat(filed), accn)


def nvda_like() -> list[Fact]:
    return [
        # current quarter + same quarter a year earlier
        F("Revenues", "2026-04-27", "2026-07-26", 96.0e9),
        F("Revenues", "2025-04-28", "2025-07-27", 46.0e9, filed="2025-08-27"),
        # YTD (6 months) must not be mistaken for the latest quarter
        F("Revenues", "2026-01-26", "2026-07-26", 177.0e9),
        F("NetIncomeLoss", "2026-04-27", "2026-07-26", 60.0e9),
        F("EarningsPerShareDiluted", "2026-04-27", "2026-07-26", 2.46, unit="USD/shares"),
        # EPS for TTM: FY + current YTD - prior YTD
        F("EarningsPerShareDiluted", "2025-01-27", "2026-01-25", 4.0, filed="2026-02-25",
          form="10-K", unit="USD/shares"),
        F("EarningsPerShareDiluted", "2026-01-26", "2026-07-26", 4.85, unit="USD/shares"),
        F("EarningsPerShareDiluted", "2025-01-27", "2025-07-27", 1.85, filed="2025-08-27",
          unit="USD/shares"),
        # FCF from YTD CFO and CapEx of the same period
        F("NetCashProvidedByUsedInOperatingActivities", "2026-01-26", "2026-07-26", 74.0e9),
        F("PaymentsToAcquirePropertyPlantAndEquipment", "2026-01-26", "2026-07-26", 4.0e9),
    ]


def test_extract_latest_quarter_and_yoy() -> None:
    f = extract("NVDA", "NVIDIA", 1045810, nvda_like(), last_close=180.0)
    assert f.period_kind == "quarter"
    assert f.period_end == date(2026, 7, 26)
    assert f.revenue == 96.0e9
    assert f.revenue_yoy == pytest.approx((96 / 46 - 1) * 100)
    assert f.net_margin == pytest.approx(62.5)
    assert f.eps_diluted == 2.46


def test_fcf_uses_matching_period() -> None:
    f = extract("NVDA", "NVIDIA", 1, nvda_like(), None)
    assert f.fcf == pytest.approx(70.0e9)
    assert (f.fcf_start, f.fcf_end) == (date(2026, 1, 26), date(2026, 7, 26))


def test_pe_ttm() -> None:
    f = extract("NVDA", "NVIDIA", 1, nvda_like(), last_close=180.0)
    assert f.eps_ttm == pytest.approx(4.0 + 4.85 - 1.85)
    assert f.pe_ttm == pytest.approx(180.0 / 7.0)


def test_negative_eps_has_no_pe() -> None:
    facts = [F("Revenues", "2025-01-01", "2025-12-31", 1e9, form="10-K"),
             F("EarningsPerShareDiluted", "2025-01-01", "2025-12-31", -0.5, form="10-K",
               unit="USD/shares")]
    f = extract("X", "X", 1, facts, last_close=10.0)
    assert f.pe_ttm is None
    assert any("P/E" in fl for fl in f.flags)


def test_restatement_uses_latest_filing() -> None:
    facts = [F("Revenues", "2025-01-01", "2025-03-31", 100.0, filed="2025-05-01", accn="a"),
             F("Revenues", "2025-01-01", "2025-03-31", 90.0, filed="2026-05-01", accn="b")]
    per = latest_per_period(facts)
    assert next(iter(per.values())).val == 90.0


def test_missing_revenue_is_flagged_not_zero() -> None:
    f = extract("X", "X", 1, [], None)
    assert f.revenue is None and f.flags


def test_parse_company_facts_filters_forms_and_units() -> None:
    data: dict[str, Any] = {"facts": {"us-gaap": {"Revenues": {"units": {
        "USD": [
            {"start": "2026-04-27", "end": "2026-07-26", "val": 5, "form": "10-Q",
             "filed": "2026-08-26", "accn": "x"},
            {"start": "2026-04-27", "end": "2026-07-26", "val": 5, "form": "8-K",
             "filed": "2026-08-26", "accn": "y"},
        ],
        "EUR": [{"start": "2026-04-27", "end": "2026-07-26", "val": 5, "form": "10-Q",
                 "filed": "2026-08-26", "accn": "z"}],
    }}}}}
    facts = parse_company_facts(data)
    assert len(facts) == 1 and facts[0].accn == "x"


def test_parse_ticker_map_and_8k() -> None:
    assert parse_ticker_map({"0": {"cik_str": 1045810, "ticker": "nvda", "title": "N"}}) == {
        "NVDA": 1045810}
    subs = {"filings": {"recent": {
        "form": ["8-K", "4", "8-K"], "filingDate": ["2026-11-17", "2026-11-16", "2026-10-01"],
        "accessionNumber": ["0001045810-26-000088", "x", "y"],
        "primaryDocument": ["nvda-20261117.htm", "d", "e"], "items": ["2.02,9.01", "", "5.02"],
    }}}
    out = parse_recent_8k(subs, 1045810, date(2026, 11, 10))
    assert len(out) == 1
    assert out[0]["url"] == ("https://www.sec.gov/Archives/edgar/data/1045810/"
                             "000104581026000088/nvda-20261117.htm")


def test_parse_fred_csv_skips_missing_values() -> None:
    csv_text = "observation_date,DGS10\n2026-11-19,4.10\n2026-11-20,.\n2026-11-21,4.05\n"
    obs = parse_fred_csv(csv_text)
    assert [o.value for o in obs] == [4.10, 4.05]


def test_macro_yoy_and_change() -> None:
    obs = [MacroObs(date(2025, m, 1), 100.0 + m) for m in range(1, 13)]
    obs += [MacroObs(date(2026, 1, 1), 104.0), MacroObs(date(2026, 2, 1), 105.0)]
    row = summarize("CPIAUCSL", "CPI", "us", "%", "yoy", obs, date(2026, 11, 23))
    assert row.last_date == date(2026, 2, 1)
    assert row.value == pytest.approx((105 / 102 - 1) * 100)
    assert row.change == pytest.approx(row.value - (104 / 101 - 1) * 100)


def test_macro_empty_is_none() -> None:
    row = summarize("DGS10", "10Y", "us", "%", "level", [], date(2026, 11, 23))
    assert row.value is None and row.change is None


class FakeSec:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def ticker_map(self) -> dict[str, int]:
        return {"NVDA": 1045810}

    def company_facts(self, cik: int) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise ConnectionError
        rows = [{"start": f.start.isoformat() if f.start else None, "end": f.end.isoformat(),
                 "val": f.val, "form": f.form, "filed": f.filed.isoformat(), "accn": f.accn}
                for f in nvda_like()]
        by: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for f, r in zip(nvda_like(), rows, strict=True):
            by.setdefault(f.concept, {}).setdefault(f.unit, []).append(r)
        return {"facts": {"us-gaap": {k: {"units": v} for k, v in by.items()}}}

    def submissions(self, cik: int) -> dict[str, Any]:
        return {"filings": {"recent": {
            "form": ["8-K"], "filingDate": ["2025-11-24"],
            "accessionNumber": ["0001045810-25-000001"], "primaryDocument": ["n.htm"],
            "items": ["2.02,9.01"]}}}


class FakeFred:
    def series(self, series_id: str, start: date) -> list[MacroObs]:
        return [MacroObs(date(2025, 11, 20), 4.1), MacroObs(date(2025, 11, 21), 4.0)]


def test_report_contains_sections_4_and_5(tmp_path: Any) -> None:
    from market_digest import pipeline
    from market_digest.config import FundamentalsConfig, MacroConfig, MacroSeriesConfig
    from market_digest.storage import Storage
    from tests.conftest import FakeCalendar, make_config
    from tests.test_pipeline import NOW, _news, _prices

    cfg = make_config(tmp_path).model_copy(update={
        "fundamentals": FundamentalsConfig(enabled=True),
        "macro": MacroConfig(enabled=True, series=(MacroSeriesConfig(id="DGS10", name="10Y"),)),
    })
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    assert pipeline.fetch_official(cfg, st, FakeSec(), FakeFred(), NOW) == {}
    res = pipeline.generate(cfg, st, FakeCalendar(), NOW)
    md = res.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    s4 = md.split("## 4.")[1].split("## 5.")[0]
    s5 = md.split("## 5.")[1].split("## 6.")[0]
    assert "NVDA" in s4 and "+108,70%" in s4 and "wyniki finansowe" in s4
    assert "sec.gov/Archives/edgar/data/1045810/000104581025000001/n.htm" in s4
    assert "10Y" in s5 and "4,00 %" in s5 and "-0,10 p.p." in s5
    assert "Moduł niedostępny" not in s4 + s5


def test_sec_outage_keeps_cached_data(tmp_path: Any) -> None:
    from datetime import timedelta

    from market_digest import pipeline
    from market_digest.config import FundamentalsConfig
    from market_digest.storage import Storage
    from tests.conftest import make_config
    from tests.test_pipeline import NOW

    cfg = make_config(tmp_path).model_copy(update={
        "fundamentals": FundamentalsConfig(enabled=True, refresh_hours=1)})
    st = Storage(cfg.app.db_path)
    pipeline.fetch_official(cfg, st, FakeSec(), None, NOW)
    later = NOW + timedelta(hours=5)
    failed = pipeline.fetch_official(cfg, st, FakeSec(fail=True), None, later)
    assert "sec:NVDA:facts" in failed
    off = pipeline.build_official(cfg, st, later, {"NVDA": 180.0})
    assert off.fundamentals and off.fundamentals[0].revenue == 96.0e9


def test_foreign_adr_not_queried_in_sec(tmp_path: Any) -> None:
    from market_digest import pipeline
    from tests.conftest import make_config

    cfg = make_config(tmp_path)
    assert [i.symbol for i in pipeline.sec_eligible(cfg)] == ["NVDA"]  # TSM (TW) excluded


def test_fcf_prefers_fiscal_ytd_over_trailing_12m() -> None:
    facts = [
        F("Revenues", "2026-07-01", "2026-09-30", 10.0),
        F("NetCashProvidedByUsedInOperatingActivities", "2025-10-01", "2026-09-30", 100.0),
        F("PaymentsToAcquirePropertyPlantAndEquipment", "2025-10-01", "2026-09-30", 150.0),
        F("NetCashProvidedByUsedInOperatingActivities", "2026-01-01", "2026-09-30", 70.0),
        F("PaymentsToAcquirePropertyPlantAndEquipment", "2026-01-01", "2026-09-30", 60.0),
    ]
    f = extract("AMZN", "Amazon", 1, facts, None)
    assert f.fcf == pytest.approx(10.0)
    assert f.fcf_start == date(2026, 1, 1)


def test_stale_fcf_period_is_flagged() -> None:
    facts = [
        F("Revenues", "2026-07-01", "2026-09-30", 10.0),
        F("NetCashProvidedByUsedInOperatingActivities", "2026-01-01", "2026-09-30", 5.0),
        F("NetCashProvidedByUsedInOperatingActivities", "2025-01-01", "2025-12-31", 8.0,
          form="10-K"),
        F("PaymentsToAcquirePropertyPlantAndEquipment", "2025-01-01", "2025-12-31", 3.0,
          form="10-K"),
    ]
    f = extract("UUUU", "Energy Fuels", 1, facts, None)
    assert f.fcf == 5.0 and f.fcf_end == date(2025, 12, 31)
    assert any("wcześniejszego okresu" in fl for fl in f.flags)


def _capex_ytd(year: int, vals: tuple[float, float, float, float]) -> list[Fact]:
    """Calendar-year issuer: 10-Q YTD for Q1..Q3 and 10-K full year."""
    c = "PaymentsToAcquirePropertyPlantAndEquipment"
    q1, h1, m9, fy = vals
    return [F(c, f"{year}-01-01", f"{year}-03-31", q1, filed=f"{year}-05-01", accn=f"{year}a"),
            F(c, f"{year}-01-01", f"{year}-06-30", h1, filed=f"{year}-08-01", accn=f"{year}b"),
            F(c, f"{year}-01-01", f"{year}-09-30", m9, filed=f"{year}-11-01", accn=f"{year}c"),
            F(c, f"{year}-01-01", f"{year}-12-31", fy, filed=f"{year + 1}-02-01", form="10-K",
              accn=f"{year}d")]


def test_quarterly_from_ytd_and_ttm() -> None:
    from market_digest.fundamentals import CAPEX, flow_stats, quarterly

    facts = _capex_ytd(2025, (10, 22, 36, 52)) + _capex_ytd(2026, (15, 32, 51, 0))[:3]
    q = quarterly(facts, CAPEX)
    assert q[date(2025, 6, 30)] == 12 and q[date(2025, 12, 31)] == 16  # Q4 = FY - 9M
    assert q[date(2026, 9, 30)] == 19
    st = flow_stats("MSFT", facts, CAPEX)
    assert st.q_end == date(2026, 9, 30) and st.q_value == 19
    assert st.q_yoy == pytest.approx((19 / 14 - 1) * 100)
    assert st.ttm == 16 + 15 + 17 + 19  # Q4'25 + Q1..Q3'26
    assert st.ttm_yoy is None  # no full year before 2025 in the fixture


def test_ttm_requires_four_quarters() -> None:
    from market_digest.fundamentals import CAPEX, flow_stats

    st = flow_stats("X", _capex_ytd(2026, (15, 32, 51, 0))[:3], CAPEX)
    assert st.q_value == 19 and st.ttm is None


def test_section_6_rendered(tmp_path: Any) -> None:
    from market_digest import pipeline
    from market_digest.config import AiConfig, FundamentalsConfig
    from market_digest.storage import Storage
    from tests.conftest import FakeCalendar, make_config
    from tests.test_pipeline import NOW, _news, _prices

    cfg = make_config(tmp_path).model_copy(update={
        "fundamentals": FundamentalsConfig(enabled=True),
        "ai": AiConfig(hyperscalers=("NVDA",), suppliers=("NVDA",)),
    })
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    pipeline.fetch_official(cfg, st, FakeSec(), None, NOW)
    md = pipeline.generate(cfg, st, FakeCalendar(), NOW).report_path.read_text(  # type: ignore[union-attr]
        encoding="utf-8")
    s6 = md.split("## 6.")[1].split("## 7.")[0]
    assert "| NVDA | 2026-07-26 | 96,0 mld USD |" in s6  # revenue quarter from fixture
    assert "nie dowodzi rentowności" in s6
    assert "Moduł niedostępny" not in s6
