"""Deterministic price metrics. Pure functions; periods are counted in sessions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from market_digest.models import PriceBar

DRAWDOWN_WINDOW_SESSIONS = 252


@dataclass(frozen=True, slots=True)
class Metrics:
    last_session: date | None
    last_close: float | None
    ret_1d: float | None
    ret_5d: float | None
    ret_21d: float | None
    ret_ytd: float | None
    drawdown_52w: float | None
    ret_21d_pln: float | None = None
    flags: tuple[str, ...] = field(default_factory=tuple)


def pct(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def _valid(bars: Sequence[PriceBar], asof: date | None) -> list[PriceBar]:
    out = [b for b in bars if b.close is not None and b.close > 0]
    if asof is not None:
        out = [b for b in out if b.session_date <= asof]
    return sorted(out, key=lambda b: b.session_date)


def session_return(bars: Sequence[PriceBar], sessions: int) -> float | None:
    """Return over ``sessions`` completed sessions of this instrument (not calendar days)."""
    if len(bars) <= sessions:
        return None
    return pct(bars[-1].close, bars[-1 - sessions].close)


def ytd_return(bars: Sequence[PriceBar]) -> float | None:
    if not bars:
        return None
    year = bars[-1].session_date.year
    prior = [b for b in bars if b.session_date.year < year]
    if not prior:
        return None
    return pct(bars[-1].close, prior[-1].close)


def drawdown_from_high(bars: Sequence[PriceBar], window: int = DRAWDOWN_WINDOW_SESSIONS) -> float | None:
    """Current vs max **adjusted** close in window; never mixes adjusted with raw prices."""
    tail = list(bars[-window:])
    if not tail:
        return None
    use_adj = all(b.adj_close is not None for b in tail)
    values = [(b.adj_close if use_adj else b.close) for b in tail]
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return pct(clean[-1], max(clean))


def fx_at(fx: Sequence[PriceBar], d: date) -> float | None:
    """Last FX observation on or before ``d``."""
    best: float | None = None
    for bar in sorted(fx, key=lambda b: b.session_date):
        if bar.session_date > d:
            break
        best = bar.close
    return best


def converted_return(
    bars: Sequence[PriceBar], fx: Sequence[PriceBar] | None, sessions: int
) -> float | None:
    """Return in reporting currency: (P1*FX1)/(P0*FX0) - 1, FX taken on both dates."""
    if fx is None or len(bars) <= sessions:
        return None
    p1, p0 = bars[-1], bars[-1 - sessions]
    fx1, fx0 = fx_at(fx, p1.session_date), fx_at(fx, p0.session_date)
    if None in (fx1, fx0, p1.close, p0.close):
        return None
    assert fx1 is not None and fx0 is not None and p1.close is not None and p0.close is not None
    return pct(p1.close * fx1, p0.close * fx0)


def compute(
    bars: Sequence[PriceBar],
    expected_session: date | None,
    fx: Sequence[PriceBar] | None = None,
) -> Metrics:
    flags: list[str] = []
    clean = _valid(bars, expected_session)
    if not clean:
        return Metrics(None, None, None, None, None, None, None, None, ("brak danych",))
    last = clean[-1]
    if expected_session is not None and last.session_date < expected_session:
        flags.append(f"nieaktualne: ostatnie dane {last.session_date.isoformat()}")
    return Metrics(
        last_session=last.session_date,
        last_close=last.close,
        ret_1d=session_return(clean, 1),
        ret_5d=session_return(clean, 5),
        ret_21d=session_return(clean, 21),
        ret_ytd=ytd_return(clean),
        drawdown_52w=drawdown_from_high(clean),
        ret_21d_pln=converted_return(clean, fx, 21),
        flags=tuple(flags),
    )


def relative(a: float | None, b: float | None) -> float | None:
    """Difference in percentage points between instrument and benchmark."""
    if a is None or b is None:
        return None
    return a - b
