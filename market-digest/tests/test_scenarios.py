from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from market_digest import analytics
from market_digest.scenarios import Indicators, evaluate
from tests.conftest import bars_from


def _ind(**kw: object) -> Indicators:
    base: dict[str, object] = dict(index_label="S&P 500", index_date=date(2026, 11, 20),
                                   vs_sma50=None, drawdown=None, ret_21d=None, vix=None,
                                   vix_date=None, spread_10y2y=None, spread_date=None,
                                   breadth_up=None, breadth_n=4)
    base.update(kw)
    return Indicators(**base)  # type: ignore[arg-type]


def test_sma_distance_needs_full_window() -> None:
    bars = bars_from([100.0] * 49 + [110.0], date(2026, 11, 20))
    assert analytics.sma_distance(bars) == pytest.approx((110 / 100.2 - 1) * 100)
    assert analytics.sma_distance(bars[1:]) is None


def test_stress_market_meets_bear_conditions() -> None:
    bull, neutral, bear = evaluate(_ind(vs_sma50=-6.0, drawdown=-11.6, ret_21d=-9.8, vix=28.4,
                                        spread_10y2y=0.28, breadth_up=0.0))
    assert len(bear.met) == 4 and bear.known == 5  # curve not inverted
    assert "Odwrócona krzywa" in bear.unmet[0].label
    assert bull.met == []
    assert neutral.met == []


def test_calm_uptrend_meets_bull_conditions() -> None:
    bull, _, bear = evaluate(_ind(vs_sma50=3.0, drawdown=-1.0, ret_21d=4.0, vix=14.0,
                                  spread_10y2y=0.5, breadth_up=0.75))
    assert len(bull.met) == 4
    assert bear.met == []


def test_missing_data_is_not_counted_as_met_or_unmet() -> None:
    bull, neutral, bear = evaluate(_ind(vix=22.0))
    assert bull.known == 1 and len(bull.unmet) == 1
    assert neutral.known == 1 and len(neutral.met) == 1
    assert bear.known == 1


def test_section_8_rendered_in_report(tmp_path: Path) -> None:
    from market_digest import pipeline
    from market_digest.storage import Storage
    from tests.conftest import FakeCalendar, make_config
    from tests.test_pipeline import NOW, _news, _prices

    cfg = make_config(tmp_path)
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    md = pipeline.generate(cfg, st, FakeCalendar(), NOW).report_path.read_text(  # type: ignore[union-attr]
        encoding="utf-8")
    s8 = md.split("## 8.")[1].split("## 9.")[0]
    assert "| Wzrostowy |" in s8 and "| Spadkowy |" in s8
    assert "nie wyliczone prawdopodobieństwa" in s8
    assert "bez danych" in s8  # no FRED in this test -> VIX and spread missing
    assert "prawdopodobieństwo " not in s8
