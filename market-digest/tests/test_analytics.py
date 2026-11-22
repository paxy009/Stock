from datetime import date

import pytest

from market_digest import analytics as a
from market_digest.models import PriceBar
from tests.conftest import bars_from

MONDAY = date(2025, 11, 24)


def test_monday_1d_compares_with_friday() -> None:
    bars = bars_from([100.0, 102.0], MONDAY)
    assert bars[0].session_date == date(2025, 11, 21)
    m = a.compute(bars, expected_session=MONDAY)
    assert m.ret_1d == pytest.approx(2.0)
    assert m.flags == ()


def test_weekend_report_shows_last_real_move_not_zero() -> None:
    friday = date(2025, 11, 21)
    m = a.compute(bars_from([100.0, 99.0], friday), expected_session=friday)
    assert m.ret_1d == pytest.approx(-1.0)
    assert m.last_session == friday


def test_sessions_not_calendar_days() -> None:
    bars = bars_from([float(100 + i) for i in range(30)], MONDAY)
    m = a.compute(bars, MONDAY)
    assert m.ret_5d == pytest.approx((129 / 124 - 1) * 100)
    assert m.ret_21d == pytest.approx((129 / 108 - 1) * 100)


def test_split_does_not_create_fake_drawdown() -> None:
    # Raw prices halve after a 2:1 split; adjusted series is continuous.
    raw = [200.0, 202.0, 101.0, 102.0]
    adj = [100.0, 101.0, 101.0, 102.0]
    m = a.compute(bars_from(raw, MONDAY, adj), MONDAY)
    assert m.drawdown_52w == pytest.approx(0.0)


def test_drawdown_never_mixes_adjusted_and_raw() -> None:
    days = bars_from([100.0, 90.0], MONDAY)
    bars = [PriceBar(days[0].session_date, 100.0, None), PriceBar(days[1].session_date, 90.0, 45.0)]
    assert a.drawdown_from_high(bars) == pytest.approx(-10.0)  # falls back to close for all


def test_missing_data_is_none_not_zero() -> None:
    m = a.compute([], MONDAY)
    assert m.ret_1d is None and m.last_close is None
    assert a.compute(bars_from([100.0], MONDAY), MONDAY).ret_1d is None


def test_stale_series_flagged() -> None:
    m = a.compute(bars_from([100.0, 101.0], date(2025, 11, 20)), MONDAY)
    assert m.flags and "nieaktualne" in m.flags[0]


def test_ytd_uses_last_close_of_previous_year() -> None:
    bars = [PriceBar(date(2024, 12, 30), 90.0), PriceBar(date(2024, 12, 31), 100.0),
            PriceBar(date(2025, 1, 2), 110.0)]
    assert a.ytd_return(bars) == pytest.approx(10.0)


def test_pln_return_uses_fx_on_both_dates() -> None:
    bars = bars_from([*([100.0] * 21), 110.0], MONDAY)
    fx = [PriceBar(bars[0].session_date, 4.0), PriceBar(bars[-1].session_date, 3.6)]
    got = a.converted_return(bars, fx, 21)
    assert got == pytest.approx(-1.0)  # (110*3.6)/(100*4.0)-1, not 10% + (-10%)


def test_pln_return_na_without_fx() -> None:
    bars = bars_from([100.0] * 22, MONDAY)
    assert a.converted_return(bars, None, 21) is None
    late_fx = [PriceBar(MONDAY, 4.0)]  # no FX for the start date
    assert a.converted_return(bars, late_fx, 21) is None


def test_relative_return() -> None:
    assert a.relative(3.0, 1.0) == pytest.approx(2.0)
    assert a.relative(None, 1.0) is None
