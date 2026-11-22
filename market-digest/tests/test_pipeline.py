"""End-to-end offline: static providers -> SQLite -> report .md with QA."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from market_digest import pipeline
from market_digest.config import Config
from market_digest.evidence import EvidencePackage
from market_digest.models import PriceBar, ReportContent, TldrItem
from market_digest.narrative import TemplateProvider, compose_with_fallback
from market_digest.providers.news import StaticNewsProvider
from market_digest.providers.prices import StaticPriceProvider
from market_digest.storage import Storage
from tests.conftest import FakeCalendar, bars_from, news

MONDAY = date(2025, 11, 24)
NOW = datetime(2025, 11, 24, 22, 30, tzinfo=UTC)  # 23:30 Warsaw


def _prices(skip: set[str] | None = None) -> StaticPriceProvider:
    skip = skip or set()
    data: dict[str, list[PriceBar]] = {}
    for sym, base in (("SPY", 500.0), ("VGK", 70.0), ("EWJ", 70.0), ("NVDA", 180.0),
                      ("TSM", 200.0)):
        if sym not in skip:
            data[sym] = bars_from([base + i for i in range(30)], MONDAY)
    data["USDPLN=X"] = bars_from([4.0] * 30, MONDAY)
    return StaticPriceProvider(data)


def _news() -> StaticNewsProvider:
    return StaticNewsProvider(
        [news("Fed statement on rates", "https://www.federalreserve.gov/x.htm",
              NOW - timedelta(hours=3))],
        errors={"boj": "ConnectError"},
    )


def _run(cfg: Config, prices: StaticPriceProvider | None = None, **kw: object) -> tuple[
        pipeline.RunResult, Storage]:
    st = Storage(cfg.app.db_path)
    failed = pipeline.fetch(cfg, st, prices or _prices(), _news(), NOW)
    res = pipeline.generate(cfg, st, FakeCalendar(), NOW, failed_sources=failed, **kw)  # type: ignore[arg-type]
    return res, st


def test_full_report_offline(cfg: Config) -> None:
    res, _ = _run(cfg)
    assert res.report_path is not None
    md = res.report_path.read_text(encoding="utf-8")
    assert res.content_status == "complete"
    assert md.startswith("# Market Digest — 2025-11-24 (poniedziałek)")
    assert "USA: 2025-11-24" in md
    assert "VGK" in md and "EWJ" in md and "ETF proxy" in md
    assert "TSM" not in md.split("## 11.")[0]  # EM ADR excluded from investment part
    assert "TSM (kraj emitenta: TW" in md
    assert "federalreserve.gov/x.htm" in md
    assert "boj (ConnectError)" in md
    assert "{{" not in md and "example.org" not in md
    assert "Moduł niedostępny" in md
    assert "niepotwierdzona" in md


def test_missing_region_marks_partial(cfg: Config) -> None:
    res, _ = _run(cfg, _prices(skip={"EWJ"}))
    md = res.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert res.content_status == "partial"
    assert "Brakujące regiony:** Japonia" in md


def test_missing_ticker_does_not_break_report(cfg: Config) -> None:
    res, _ = _run(cfg, _prices(skip={"NVDA"}))
    md = res.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert "ceny:NVDA" in md
    assert "NVDA (brak danych)" in md  # flagged, not 0%


def test_rerun_with_same_data_is_idempotent(cfg: Config) -> None:
    _, st = _run(cfg)
    again = pipeline.generate(cfg, st, FakeCalendar(), NOW,
                              failed_sources={"rss:boj": "ConnectError"})
    assert again.skipped_unchanged
    assert st.next_report_version(MONDAY) == 2


def test_same_snapshot_gives_same_metrics_section(cfg: Config, tmp_path: Path) -> None:
    res1, st = _run(cfg)
    md1 = res1.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    res2 = pipeline.generate(cfg, st, FakeCalendar(), NOW, force=True,
                             failed_sources={"rss:boj": "ConnectError"})
    md2 = res2.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    section = lambda md: md.split("## 1.")[1].split("## 2.")[0]  # noqa: E731
    assert section(md1) == section(md2)


def test_saturday_report_shows_friday_sessions(cfg: Config) -> None:
    sat = datetime(2025, 11, 22, 22, 30, tzinfo=UTC)
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), StaticNewsProvider([]), sat)
    res = pipeline.generate(cfg, st, FakeCalendar(), sat)
    md = res.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert "(sobota)" in md and "USA: 2025-11-21" in md
    assert "USA: weekend" in md


def test_us_holiday_keeps_last_session_without_fake_zero(cfg: Config) -> None:
    holiday = {"XNYS": {MONDAY}}
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), StaticNewsProvider([]), NOW)
    ev = pipeline.build_evidence(cfg, st, FakeCalendar(holiday), NOW, "r1")
    spy = next(r for r in ev.rows if r.symbol == "SPY")
    assert spy.metrics.last_session == date(2025, 11, 21)
    assert spy.metrics.ret_1d is not None and spy.metrics.ret_1d != 0.0


class _EvilLLM:
    name = "fake"

    def compose(self, evidence: EvidencePackage) -> ReportContent:
        return ReportContent("llm", (TldrItem("x", "https://made-up.example.net/a"),), "y")


class _BrokenLLM:
    name = "broken"

    def compose(self, evidence: EvidencePackage) -> ReportContent:
        raise TimeoutError


@pytest.mark.parametrize("llm", [_EvilLLM(), _BrokenLLM()])
def test_llm_failure_or_invented_url_falls_back_to_template(cfg: Config, llm: object) -> None:
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    ev = pipeline.build_evidence(cfg, st, FakeCalendar(), NOW, "r1")
    content = compose_with_fallback(llm, ev)  # type: ignore[arg-type]
    assert content.generation_mode == "template_fallback"
    assert all(i.url in ev.allowed_urls() for i in content.tldr if i.url)


def test_template_without_llm_is_complete(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    ev = pipeline.build_evidence(cfg, st, FakeCalendar(), NOW, "r1")
    content = TemplateProvider().compose(ev)
    assert 3 <= len(content.tldr) <= 5
