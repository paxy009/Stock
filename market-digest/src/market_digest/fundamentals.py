"""Deterministic extraction of reported fundamentals from SEC XBRL facts (US-GAAP)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise

REVENUE = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
           "RevenuesNetOfInterestExpense", "SalesRevenueNet")
NET_INCOME = ("NetIncomeLoss",)
EPS_DILUTED = ("EarningsPerShareDiluted",)
CFO = ("NetCashProvidedByUsedInOperatingActivities",)
CAPEX = ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets")
ALL_CONCEPTS = frozenset(REVENUE + NET_INCOME + EPS_DILUTED + CFO + CAPEX)

QUARTER = (80, 100)
ANNUAL = (350, 380)


@dataclass(frozen=True, slots=True)
class Fact:
    concept: str
    unit: str
    start: date | None
    end: date
    val: float
    fy: int | None
    fp: str | None
    form: str
    filed: date
    accn: str

    @property
    def days(self) -> int | None:
        return (self.end - self.start).days if self.start else None


@dataclass(frozen=True, slots=True)
class Fundamentals:
    ticker: str
    name: str
    cik: int
    period_kind: str | None  # quarter | annual
    period_start: date | None
    period_end: date | None
    form: str | None
    filed: date | None
    revenue: float | None
    revenue_yoy: float | None
    net_income: float | None
    eps_diluted: float | None
    net_margin: float | None
    fcf: float | None
    fcf_start: date | None
    fcf_end: date | None
    eps_ttm: float | None
    pe_ttm: float | None
    source_url: str
    flags: tuple[str, ...] = field(default_factory=tuple)


def _kind(days: int | None) -> str | None:
    if days is None:
        return None
    if QUARTER[0] <= days <= QUARTER[1]:
        return "quarter"
    if ANNUAL[0] <= days <= ANNUAL[1]:
        return "annual"
    return None


def latest_per_period(facts: Iterable[Fact]) -> dict[tuple[date | None, date], Fact]:
    """One value per (start, end): the most recently filed one (handles restatements)."""
    out: dict[tuple[date | None, date], Fact] = {}
    for f in facts:
        key = (f.start, f.end)
        cur = out.get(key)
        if cur is None or (f.filed, f.accn) > (cur.filed, cur.accn):
            out[key] = f
    return out


def _by_concepts(facts: Sequence[Fact], concepts: tuple[str, ...]) -> list[Fact]:
    return [f for f in facts if f.concept in concepts]


def _exact(facts: Sequence[Fact], concepts: tuple[str, ...], start: date | None,
           end: date) -> Fact | None:
    per = latest_per_period(_by_concepts(facts, concepts))
    return per.get((start, end))


def _year_earlier(cands: Iterable[Fact], ref: Fact) -> Fact | None:
    best: Fact | None = None
    for f in cands:
        if f.days is None or ref.days is None or abs(f.days - ref.days) > 10:
            continue
        if abs((ref.end - f.end).days - 365) <= 10 and (best is None or f.filed > best.filed):
            best = f
    return best


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100.0


def latest_revenue(facts: Sequence[Fact]) -> Fact | None:
    cands = [f for f in latest_per_period(_by_concepts(facts, REVENUE)).values()
             if _kind(f.days) is not None]
    if not cands:
        return None
    # latest end; on the same end prefer the quarter over the fiscal year
    return max(cands, key=lambda f: (f.end, _kind(f.days) == "quarter", f.filed))


def eps_ttm(facts: Sequence[Fact]) -> tuple[float | None, str | None]:
    """TTM diluted EPS = last FY + current YTD - prior-year YTD (approximation)."""
    per = list(latest_per_period(_by_concepts(facts, EPS_DILUTED)).values())
    annual = [f for f in per if _kind(f.days) == "annual"]
    if not annual:
        return None, None
    fy = max(annual, key=lambda f: f.end)
    ytd = [f for f in per
           if f.start is not None and 0 < (f.start - fy.end).days <= 7
           and f.end > fy.end and f.days is not None and f.days < 350]
    if not ytd:
        return fy.val, "TTM = ostatni rok obrotowy"
    cur = max(ytd, key=lambda f: f.end)
    prev = _year_earlier(per, cur)
    if prev is None:
        return fy.val, "TTM = ostatni rok obrotowy (brak porównywalnego YTD)"
    return fy.val + cur.val - prev.val, "TTM ≈ FY + YTD − YTD r/r (przybliżenie)"


def extract(ticker: str, name: str, cik: int, facts: Sequence[Fact],
            last_close: float | None) -> Fundamentals:
    flags: list[str] = []
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"
    rev = latest_revenue(facts)
    if rev is None:
        return Fundamentals(ticker, name, cik, None, None, None, None, None, None, None, None,
                            None, None, None, None, None, None, None, url,
                            ("brak przychodów w XBRL",))
    prior = _year_earlier(latest_per_period(_by_concepts(facts, REVENUE)).values(), rev)
    ni = _exact(facts, NET_INCOME, rev.start, rev.end)
    eps = _exact(facts, EPS_DILUTED, rev.start, rev.end)
    margin = (ni.val / rev.val * 100.0) if ni and rev.val else None

    cfo_all = latest_per_period(_by_concepts(facts, CFO))
    fcf = fcf_start = fcf_end = None
    # Same window convention for all issuers: latest end date, prefer fiscal YTD (<1y) over
    # trailing-12M windows that some filers (e.g. AMZN) also tag in 10-Q.
    ranked = sorted(cfo_all.items(),
                    key=lambda kv: (kv[0][1], (kv[1].days or 999) < 350, kv[1].days or 0),
                    reverse=True)
    for (start, end), c in ranked:
        capex = _exact(facts, CAPEX, start, end)
        if capex is not None:
            fcf, fcf_start, fcf_end = c.val - capex.val, start, end
            break
    if fcf is None:
        flags.append("FCF: brak spójnych CFO i CapEx")
    elif fcf_end is not None and rev.end is not None and fcf_end < rev.end:
        flags.append(f"FCF z wcześniejszego okresu (do {fcf_end.isoformat()}) — brak CapEx "
                     "dla najnowszego okresu")

    ttm, ttm_note = eps_ttm(facts)
    pe = None
    if ttm is not None and ttm <= 0:
        flags.append("EPS TTM ≤ 0 — P/E nie ma sensu")
    elif ttm is not None and last_close is not None:
        pe = last_close / ttm
    # The standard FY+YTD approximation is described in the methodology note; flag only deviations.
    if ttm_note and not ttm_note.startswith("TTM ≈"):
        flags.append(ttm_note)
    if ni is None:
        flags.append("zysk netto: brak NetIncomeLoss dla tego okresu")
    return Fundamentals(
        ticker=ticker, name=name, cik=cik, period_kind=_kind(rev.days),
        period_start=rev.start, period_end=rev.end, form=rev.form, filed=rev.filed,
        revenue=rev.val, revenue_yoy=_pct(rev.val, prior.val if prior else None),
        net_income=ni.val if ni else None, eps_diluted=eps.val if eps else None,
        net_margin=margin, fcf=fcf, fcf_start=fcf_start, fcf_end=fcf_end, eps_ttm=ttm,
        pe_ttm=pe, source_url=url, flags=tuple(flags),
    )


# --- Sekcja 6: przepływy kwartalne i TTM (CapEx, przychody) -------------------------------


@dataclass(frozen=True, slots=True)
class FlowStats:
    ticker: str
    concept: str | None
    q_end: date | None
    q_value: float | None
    q_yoy: float | None
    ttm: float | None
    ttm_yoy: float | None


def _pick_concept(facts: Sequence[Fact], concepts: tuple[str, ...]) -> list[Fact]:
    """Concept with the most recent period end (issuers switch tags over time)."""
    best: list[Fact] = []
    best_end: date | None = None
    for c in concepts:
        fs = [f for f in facts if f.concept == c and f.start is not None]
        if not fs:
            continue
        end = max(f.end for f in fs)
        if best_end is None or end > best_end:
            best, best_end = fs, end
    return best


def quarterly(facts: Sequence[Fact], concepts: tuple[str, ...]) -> dict[date, float]:
    """Quarter values by period end. Cash-flow tags are year-to-date in 10-Q, so a quarter is
    derived as YTD(end) − YTD(previous end) with the same fiscal-year start (Q4 = FY − 9M)."""
    items = list(latest_per_period(_pick_concept(facts, concepts)).values())
    q: dict[date, float] = {f.end: f.val for f in items if _kind(f.days) == "quarter"}
    by_start: dict[date, list[Fact]] = {}
    for f in items:
        if f.start is not None:
            by_start.setdefault(f.start, []).append(f)
    for group in by_start.values():
        group.sort(key=lambda f: f.end)
        for prev, cur in pairwise(group):
            gap = (cur.end - prev.end).days
            if QUARTER[0] <= gap <= QUARTER[1] and cur.end not in q:
                q[cur.end] = cur.val - prev.val
    return q


def _near(q: dict[date, float], target: date, tol: int) -> date | None:
    if not q:
        return None
    best = min(q, key=lambda d: abs((d - target).days))
    return best if abs((best - target).days) <= tol else None


def ttm_sum(q: dict[date, float], end: date) -> float | None:
    """Sum of 4 consecutive quarters ending at ``end``; None if any quarter is missing."""
    ends = [end]
    for _ in range(3):
        prev = _near(q, ends[-1] - timedelta(days=91), 12)
        if prev is None or prev >= ends[-1]:
            return None
        ends.append(prev)
    return sum(q[e] for e in ends)


def flow_stats(ticker: str, facts: Sequence[Fact], concepts: tuple[str, ...]) -> FlowStats:
    q = quarterly(facts, concepts)
    picked = _pick_concept(facts, concepts)
    concept = picked[0].concept if picked else None
    if not q:
        return FlowStats(ticker, concept, None, None, None, None, None)
    end = max(q)
    prev = _near(q, end - timedelta(days=364), 10)
    ttm = ttm_sum(q, end)
    ttm_prev = ttm_sum(q, prev) if prev else None
    return FlowStats(ticker, concept, end, q[end], _pct(q[end], q[prev]) if prev else None,
                     ttm, _pct(ttm, ttm_prev))


@dataclass(frozen=True, slots=True)
class AiData:
    hyperscalers: list[tuple[FlowStats, FlowStats]]  # (capex, revenue)
    suppliers: list[FlowStats]  # revenue
