"""Price providers. yfinance is a research/personal-use prototype source (see README)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from market_digest.models import PriceBar

log = logging.getLogger(__name__)

YFINANCE_SOURCE_ID = "yfinance"


@dataclass(frozen=True, slots=True)
class PriceResult:
    symbol: str
    bars: tuple[PriceBar, ...]
    error: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.bars) and self.error is None


class PriceProvider(Protocol):
    source_id: str

    def fetch(self, symbols: list[str], start: date, end: date) -> dict[str, PriceResult]: ...


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def frame_to_bars(df: Any) -> tuple[PriceBar, ...]:
    """Convert a single-ticker yfinance DataFrame (auto_adjust=False) to bars.

    yfinance 'Close' is split-adjusted, 'Adj Close' additionally dividend-adjusted.
    """
    bars: list[PriceBar] = []
    if df is None or len(df) == 0:
        return ()
    for idx, row in df.iterrows():
        bars.append(
            PriceBar(
                session_date=idx.date(),
                open=_num(row.get("Open")),
                high=_num(row.get("High")),
                low=_num(row.get("Low")),
                close=_num(row.get("Close")),
                adj_close=_num(row.get("Adj Close")),
                volume=_num(row.get("Volume")),
            )
        )
    return tuple(b for b in bars if b.close is not None)


class YFinanceProvider:
    source_id = YFINANCE_SOURCE_ID

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self, symbols: list[str], start: date, end: date) -> dict[str, PriceResult]:
        import yfinance as yf

        out: dict[str, PriceResult] = {}
        for symbol in symbols:
            try:
                df = yf.Ticker(symbol).history(
                    start=start.isoformat(),
                    end=(end + timedelta(days=1)).isoformat(),
                    auto_adjust=False,
                    actions=False,
                    timeout=self.timeout,
                )
                bars = frame_to_bars(df)
                out[symbol] = PriceResult(symbol, bars, None if bars else "pusta odpowiedź")
            except Exception as exc:  # one ticker must not break the run
                log.warning("yfinance %s: %s", symbol, exc)
                out[symbol] = PriceResult(symbol, (), f"{type(exc).__name__}")
        return out


class StaticPriceProvider:
    """Offline provider used in tests and `--offline` runs."""

    source_id = YFINANCE_SOURCE_ID

    def __init__(self, data: dict[str, list[PriceBar]]) -> None:
        self.data = data

    def fetch(self, symbols: list[str], start: date, end: date) -> dict[str, PriceResult]:
        out: dict[str, PriceResult] = {}
        for s in symbols:
            bars = tuple(b for b in self.data.get(s, []) if start <= b.session_date <= end)
            out[s] = PriceResult(s, bars, None if bars else "brak danych")
        return out
