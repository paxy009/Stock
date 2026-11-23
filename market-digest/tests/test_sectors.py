from __future__ import annotations

from pathlib import Path
from typing import Any

from market_digest import pipeline
from market_digest.models import PriceBar
from market_digest.providers.news import StaticNewsProvider
from market_digest.providers.prices import StaticPriceProvider
from market_digest.storage import Storage
from tests.conftest import FakeCalendar, bars_from, default_instruments, make_config
from tests.test_pipeline import MONDAY, NOW

SECTOR_INSTRUMENTS: list[dict[str, Any]] = [
    {"symbol": "CL=F", "name": "Ropa WTI", "kind": "future", "region": "global",
     "currency": "USD", "exchange": "XNYS", "sector": "commodities"},
    {"symbol": "XLE", "name": "Energy SPDR", "kind": "etf", "region": "us", "currency": "USD",
     "exchange": "XNYS", "exposure_countries": ["US"], "role": "benchmark_only",
     "sector": "energy"},
    {"symbol": "CCJ", "name": "Cameco", "kind": "equity", "region": "other_developed",
     "currency": "USD", "exchange": "XNYS", "issuer_country": "CA", "sector": "uranium"},
    {"symbol": "URA", "name": "Uranium ETF", "kind": "etf", "region": "global",
     "currency": "USD", "exchange": "XNYS", "exposure_countries": ["CA", "KZ"],
     "sector": "uranium"},
]


def _md(tmp_path: Path, oil: list[float]) -> str:
    cfg = make_config(tmp_path, default_instruments() + SECTOR_INSTRUMENTS)
    data: dict[str, list[PriceBar]] = {
        s: bars_from([100.0 + i * 0.1 for i in range(30)], MONDAY)
        for s in ("SPY", "VGK", "EWJ", "NVDA", "XLE", "CCJ", "URA")
    }
    data["CL=F"] = bars_from(oil, MONDAY)
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, StaticPriceProvider(data), StaticNewsProvider([]), NOW)
    res = pipeline.generate(cfg, st, FakeCalendar(), NOW)
    return res.report_path.read_text(encoding="utf-8")  # type: ignore[union-attr]


def test_section_7_table_and_significant_move(tmp_path: Path) -> None:
    md = _md(tmp_path, [70.0] * 28 + [70.0, 66.5])  # -5% in one session
    s7 = md.split("## 7.")[1].split("## 8.")[0]
    assert "| Surowce (kontrakty terminowe) | Ropa WTI (CL=F) · kontrakt ciągły | USD |" in s7
    assert "| Energia | Energy SPDR (XLE) · ETF |" in s7
    assert "| Uran i energetyka jądrowa | Cameco (CCJ) |" in s7
    assert "**Największe ruchy** (1/" in s7 and "CL=F -5,00%" in s7
    assert "nie są ceną spot" in s7


def test_em_heavy_sector_etf_excluded_and_not_in_section_1(tmp_path: Path) -> None:
    md = _md(tmp_path, [70.0] * 30)
    s1 = md.split("## 1.")[1].split("## 2.")[0]
    s7 = md.split("## 7.")[1].split("## 8.")[0]
    assert "(URA)" not in s7  # exposure includes KZ (EM); "URA" alone appears in the footnote
    assert "XLE" not in s1 and "CL=F" not in s1  # sector rows live in section 7 only
    assert "Brak istotnych ruchów" in s7


def test_no_sector_instruments_gives_short_note(cfg: Any) -> None:
    st = Storage(cfg.app.db_path)
    data = {s: bars_from([100.0] * 30, MONDAY) for s in ("SPY", "VGK", "EWJ")}
    pipeline.fetch(cfg, st, StaticPriceProvider(data), StaticNewsProvider([]), NOW)
    md = pipeline.generate(cfg, st, FakeCalendar(), NOW).report_path.read_text(  # type: ignore[union-attr]
        encoding="utf-8")
    assert "Brak danych sektorowych" in md.split("## 7.")[1].split("## 8.")[0]
