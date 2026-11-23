"""Section 2: what changed since the previous archived report (pure comparison of snapshots)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from market_digest.evidence import EvidencePackage

CORRECTION_THRESHOLD_PCT = 1.0
CloseLookup = Callable[[str, date], float | None]


@dataclass(frozen=True, slots=True)
class Change:
    area: str
    before: str
    now: str
    meaning: str


@dataclass(slots=True)
class ChangeSet:
    prev_report_date: str | None
    rows: list[Change] = field(default_factory=list)
    unchanged_sessions: list[str] = field(default_factory=list)
    new_events: list[tuple[str, str, str]] = field(default_factory=list)  # title, source, url
    followups: list[tuple[str, int, str]] = field(default_factory=list)  # title, +n, url
    new_filings: list[tuple[str, str]] = field(default_factory=list)  # label, url
    corrections: list[str] = field(default_factory=list)


def _num(v: float | None) -> str:
    return "N/A" if v is None else f"{v:,.2f}".replace(",", " ").replace(".", ",")


def _pct(v: float) -> str:
    return f"{v:+.2f}%".replace(".", ",")


def _money(v: float | None) -> str:
    return "N/A" if v is None else f"{v / 1e9:,.1f} mld USD".replace(",", " ").replace(".", ",")


def _d(v: Any) -> date | None:
    return date.fromisoformat(v) if isinstance(v, str) else None


def compute_changes(prev: tuple[date, str] | None, ev: EvidencePackage,
                    close_on: CloseLookup) -> ChangeSet:
    if prev is None:
        return ChangeSet(None)
    p: dict[str, Any] = json.loads(prev[1])
    cs = ChangeSet(prev[0].isoformat())

    if p.get("content_status") and p["content_status"] != ev.content_status:
        cs.rows.append(Change("Status raportu", p["content_status"], ev.content_status,
                              "zmiana kompletności danych regionalnych"))

    _prices(p, ev, close_on, cs)
    _macro(p, ev, cs)
    _fundamentals(p, ev, cs)

    prev_events = {e["event_id"]: e for e in p.get("events", [])}
    for e in ev.events:
        pe = prev_events.get(e.event_id)
        if pe is None:
            cs.new_events.append((e.title, e.source_name, e.url))
        elif len(e.items) > len(pe.get("items", [])):
            cs.followups.append((e.title, len(e.items) - len(pe.get("items", [])), e.url))
    prev_filings = {f["url"] for f in p.get("filings", [])}
    for fl in ev.filings:
        if fl["url"] not in prev_filings:
            cs.new_filings.append((f"{fl['ticker']} 8-K ({fl['filed']}): {fl['items']}",
                                   fl["url"]))
    return cs


def _prices(p: dict[str, Any], ev: EvidencePackage, close_on: CloseLookup,
            cs: ChangeSet) -> None:
    prev_rows = {r["symbol"]: r for r in p.get("rows", [])}
    for r in ev.rows:
        if r.kind not in ("etf", "index") or r.eligibility != "eligible":
            continue
        pr = prev_rows.get(r.symbol)
        now_d, now_c = r.metrics.last_session, r.metrics.last_close
        if pr is None or now_d is None or now_c is None:
            continue
        prev_d = _d(pr["metrics"].get("last_session"))
        prev_c = pr["metrics"].get("last_close")
        if prev_d is None or prev_c is None:
            continue
        if now_d <= prev_d:
            cs.unchanged_sessions.append(r.symbol)
            continue
        # Base the move on the provider's *current* close for the previous date, so splits or
        # data corrections since the previous report don't create fake moves.
        base = close_on(r.symbol, prev_d) or prev_c
        if base and abs(base / prev_c - 1) * 100 > CORRECTION_THRESHOLD_PCT:
            cs.corrections.append(
                f"{r.symbol}: kurs z {prev_d.isoformat()} zmieniony u dostawcy "
                f"{_num(prev_c)} → {_num(base)} (split/korekta danych)")
        cs.rows.append(Change(
            f"{r.symbol} ({r.currency})", f"{_num(base)} ({prev_d.isoformat()})",
            f"{_num(now_c)} ({now_d.isoformat()})",
            f"{_pct((now_c / base - 1) * 100)} między raportami"))


def _macro(p: dict[str, Any], ev: EvidencePackage, cs: ChangeSet) -> None:
    prev_macro = {m["series_id"]: m for m in p.get("macro", [])}
    for m in ev.macro:
        pm = prev_macro.get(m.series_id)
        if m.value is None or pm is None or pm.get("value") is None:
            continue
        prev_d = _d(pm.get("last_date"))
        if prev_d == m.last_date:
            if abs(float(pm["value"]) - m.value) > 1e-9:
                cs.corrections.append(
                    f"{m.name}: rewizja wartości za {m.last_date} "
                    f"{_num(pm['value'])} → {_num(m.value)}")
            continue
        diff = m.value - float(pm["value"])
        unit = " p.p." if m.unit == "%" else ""
        cs.rows.append(Change(
            m.name, f"{_num(pm['value'])} ({prev_d.isoformat() if prev_d else 'N/A'})",
            f"{_num(m.value)} ({m.last_date.isoformat() if m.last_date else 'N/A'})",
            f"nowa obserwacja; {diff:+.2f}".replace(".", ",") + unit))


def _fundamentals(p: dict[str, Any], ev: EvidencePackage, cs: ChangeSet) -> None:
    prev_f = {f["ticker"]: f for f in p.get("fundamentals", [])}
    for f in ev.fundamentals:
        pf = prev_f.get(f.ticker)
        if pf is None or f.period_end is None:
            continue
        prev_end = _d(pf.get("period_end"))
        if prev_end != f.period_end:
            yoy = f"; r/r {_pct(f.revenue_yoy)}" if f.revenue_yoy is not None else ""
            cs.rows.append(Change(
                f"{f.ticker} — wyniki", f"okres do {prev_end.isoformat() if prev_end else 'N/A'}",
                f"okres do {f.period_end.isoformat()}: przychody {_money(f.revenue)}{yoy}",
                f"nowy raport okresowy ({f.form} {f.filed.isoformat() if f.filed else ''})"))
        elif pf.get("revenue") is not None and f.revenue is not None and \
                abs(float(pf["revenue"]) - f.revenue) > 0.5:
            cs.corrections.append(
                f"{f.ticker}: przychody za okres do {f.period_end.isoformat()} skorygowane "
                f"{_money(pf['revenue'])} → {_money(f.revenue)}")
