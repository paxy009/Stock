"""Section 8: rule-based scenario conditions. Observable conditions only — no probabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from market_digest.analytics import Metrics

# Conventional thresholds (documented in the report footnote, not calibrated forecasts).
VIX_CALM = 20.0
VIX_STRESS = 25.0
CORRECTION_DD = -10.0  # common "correction" convention
NEAR_HIGH_DD = -5.0
BREADTH_SHARE = 0.6
FLAT_21D = 3.0


@dataclass(frozen=True, slots=True)
class Condition:
    label: str
    value: str
    met: bool | None  # None = no data


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    conditions: tuple[Condition, ...]

    @property
    def met(self) -> list[Condition]:
        return [c for c in self.conditions if c.met]

    @property
    def unmet(self) -> list[Condition]:
        return [c for c in self.conditions if c.met is False]

    @property
    def known(self) -> int:
        return sum(1 for c in self.conditions if c.met is not None)


@dataclass(frozen=True, slots=True)
class Indicators:
    index_label: str
    index_date: date | None
    vs_sma50: float | None
    drawdown: float | None
    ret_21d: float | None
    vix: float | None
    vix_date: date | None
    spread_10y2y: float | None
    spread_date: date | None
    breadth_up: float | None  # share of regional benchmarks with positive 5-session return
    breadth_n: int


def _f(v: float | None, unit: str = "%") -> str:
    if v is None:
        return "brak danych"
    s = f"{v:+.2f}" if unit in ("%", " p.p.") else f"{v:.2f}"
    return s.replace(".", ",") + unit


def _cmp(v: float | None, pred: bool) -> bool | None:
    return None if v is None else pred


def evaluate(ind: Indicators) -> list[Scenario]:
    sma, dd, r21, vix, spr, br = (ind.vs_sma50, ind.drawdown, ind.ret_21d, ind.vix,
                                  ind.spread_10y2y, ind.breadth_up)
    idx = ind.index_label
    sma_txt = f"{idx} vs średnia 50 sesji: {_f(sma)}"
    dd_txt = f"{idx} od szczytu 52 tyg.: {_f(dd)}"
    vix_txt = f"VIX: {_f(vix, '')}"
    br_txt = ("brak danych" if br is None
              else f"{round(br * ind.breadth_n)}/{ind.breadth_n} regionów z dodatnim wynikiem 5 sesji")
    spr_txt = f"10Y − 2Y: {_f(spr, ' p.p.')}"
    r21_txt = f"{idx} 21 sesji: {_f(r21)}"

    bull = Scenario("Wzrostowy", (
        Condition(f"{idx} powyżej średniej 50 sesji", sma_txt, _cmp(sma, (sma or 0) > 0)),
        Condition(f"VIX poniżej {VIX_CALM:.0f}", vix_txt, _cmp(vix, (vix or 0) < VIX_CALM)),
        Condition(f"{idx} w odległości do {abs(NEAR_HIGH_DD):.0f}% od szczytu", dd_txt,
                  _cmp(dd, (dd or 0) > NEAR_HIGH_DD)),
        Condition(f"≥{BREADTH_SHARE:.0%} regionów rośnie (5 sesji)", br_txt,
                  _cmp(br, (br or 0) >= BREADTH_SHARE)),
    ))
    neutral = Scenario("Neutralny", (
        Condition(f"{idx} w przedziale ±{FLAT_21D:.0f}% w 21 sesjach", r21_txt,
                  _cmp(r21, abs(r21 or 0) <= FLAT_21D)),
        Condition(f"VIX między {VIX_CALM:.0f} a {VIX_STRESS:.0f}", vix_txt,
                  _cmp(vix, VIX_CALM <= (vix or 0) <= VIX_STRESS)),
        Condition(f"{idx} w odległości ±{FLAT_21D:.0f}% od średniej 50 sesji", sma_txt,
                  _cmp(sma, abs(sma or 0) <= FLAT_21D)),
    ))
    bear = Scenario("Spadkowy", (
        Condition(f"{idx} poniżej średniej 50 sesji", sma_txt, _cmp(sma, (sma or 0) < 0)),
        Condition(f"VIX powyżej {VIX_STRESS:.0f}", vix_txt, _cmp(vix, (vix or 0) > VIX_STRESS)),
        Condition(f"{idx} ≥{abs(CORRECTION_DD):.0f}% poniżej szczytu (umowna korekta)", dd_txt,
                  _cmp(dd, (dd or 0) <= CORRECTION_DD)),
        Condition(f"≥{BREADTH_SHARE:.0%} regionów spada (5 sesji)", br_txt,
                  _cmp(br, (1 - (br or 0)) >= BREADTH_SHARE)),
        Condition("Odwrócona krzywa (10Y < 2Y)", spr_txt, _cmp(spr, (spr or 0) < 0)),
    ))
    return [bull, neutral, bear]


def indicators_from(ev: Any) -> Indicators:
    rows = {r.symbol: r for r in ev.rows if r.eligibility == "eligible"}
    idx_row = rows.get("^GSPC") or rows.get("SPY")
    m: Metrics | None = idx_row.metrics if idx_row else None
    label = "S&P 500" if idx_row is not None and idx_row.symbol == "^GSPC" else "SPY"

    macro = {x.series_id: x for x in ev.macro if x.value is not None}
    vix = macro.get("VIXCLS")
    t10, t2 = macro.get("DGS10"), macro.get("DGS2")
    spread = spread_date = None
    if t10 and t2 and t10.last_date == t2.last_date:
        spread, spread_date = t10.value - t2.value, t10.last_date

    # One benchmark per region: prefer local index, then the regional ETF proxy.
    per_region: dict[str, float] = {}
    for r in sorted(ev.rows, key=lambda x: (x.kind != "index", x.symbol)):
        if (r.eligibility == "eligible" and r.sector is None and r.kind in ("etf", "index")
                and r.region != "global" and r.region not in per_region
                and r.metrics.ret_5d is not None):
            per_region[r.region] = r.metrics.ret_5d
    breadth = (sum(1 for v in per_region.values() if v > 0) / len(per_region)
               if per_region else None)
    return Indicators(
        index_label=label, index_date=m.last_session if m else None,
        vs_sma50=m.vs_sma50 if m else None, drawdown=m.drawdown_52w if m else None,
        ret_21d=m.ret_21d if m else None,
        vix=vix.value if vix else None, vix_date=vix.last_date if vix else None,
        spread_10y2y=spread, spread_date=spread_date,
        breadth_up=breadth, breadth_n=len(per_region),
    )
