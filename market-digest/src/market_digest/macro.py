"""Macro series helpers (FRED). Observation period and value only; vintage not tracked yet."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class MacroObs:
    obs_date: date
    value: float


@dataclass(frozen=True, slots=True)
class MacroRow:
    series_id: str
    name: str
    region: str
    unit: str
    transform: str  # level | yoy
    last_date: date | None
    value: float | None
    prev_date: date | None
    prev_value: float | None
    source_url: str

    @property
    def change(self) -> float | None:
        if self.value is None or self.prev_value is None:
            return None
        return self.value - self.prev_value


def yoy_series(obs: Sequence[MacroObs]) -> list[MacroObs]:
    """Year-over-year % change for monthly data: matches same month a year earlier."""
    by_month = {(o.obs_date.year, o.obs_date.month): o for o in obs}
    out: list[MacroObs] = []
    for o in sorted(obs, key=lambda x: x.obs_date):
        prev = by_month.get((o.obs_date.year - 1, o.obs_date.month))
        if prev is not None and prev.value != 0:
            out.append(MacroObs(o.obs_date, (o.value / prev.value - 1.0) * 100.0))
    return out


def summarize(series_id: str, name: str, region: str, unit: str, transform: str,
              obs: Sequence[MacroObs], asof: date) -> MacroRow:
    url = f"https://fred.stlouisfed.org/series/{series_id}"
    clean = sorted((o for o in obs if o.obs_date <= asof), key=lambda o: o.obs_date)
    if transform == "yoy":
        clean = yoy_series(clean)
    if not clean:
        return MacroRow(series_id, name, region, unit, transform, None, None, None, None, url)
    last = clean[-1]
    prev = clean[-2] if len(clean) > 1 else None
    return MacroRow(series_id, name, region, unit, transform, last.obs_date, last.value,
                    prev.obs_date if prev else None, prev.value if prev else None, url)
