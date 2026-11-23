"""Orchestrates fetch -> store -> analyze -> evidence -> narrative -> render -> QA -> atomic write."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from datetime import date as date_t
from pathlib import Path
from typing import Protocol

from market_digest import analytics
from market_digest.calendar import SessionCalendar, local_date
from market_digest.changes import compute_changes
from market_digest.config import Config, InstrumentConfig
from market_digest.delivery import Mailer, build_message, send_with_retry
from market_digest.eligibility import classify
from market_digest.events import group_events, rank_events
from market_digest.evidence import EvidencePackage, InstrumentRow, RegionStatus, decide_status
from market_digest.fundamentals import Fact, Fundamentals, extract
from market_digest.macro import MacroObs, MacroRow, summarize
from market_digest.models import Eligibility
from market_digest.narrative import LLMProvider, TemplateProvider, compose_with_fallback
from market_digest.providers.news import NewsProvider
from market_digest.providers.official import (
    SEC_TICKERS_URL,
    FredProvider,
    SecProvider,
    parse_company_facts,
    parse_recent_8k,
)
from market_digest.providers.prices import PriceProvider
from market_digest.qa import validate_markdown
from market_digest.renderer import render
from market_digest.storage import Storage
from market_digest.upcoming import (
    UpcomingEvent,
    closures,
    earnings_events,
    parse_ecb,
    parse_fomc,
    within,
)

log = logging.getLogger(__name__)

REGION_EXCHANGE = {
    "us": "XNYS",
    "developed_europe": "XETR",
    "developed_asia": "XTKS",
    "other_developed": "XTSE",
}
YAHOO_URL = "https://finance.yahoo.com/"


class ReportQAError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RunResult:
    report_path: Path | None
    content_status: str
    generation_mode: str
    skipped_unchanged: bool
    problems: tuple[str, ...] = ()


def config_hash(cfg: Config) -> str:
    return hashlib.sha256(cfg.model_dump_json().encode()).hexdigest()[:16]


def active_symbols(cfg: Config) -> list[str]:
    return [i.symbol for i in cfg.instruments if i.verified]


def fetch(cfg: Config, storage: Storage, prices: PriceProvider, news: NewsProvider,
          now_utc: datetime) -> dict[str, str]:
    """Fetch and persist raw data. Returns failed sources (never raises on single failures)."""
    failed: dict[str, str] = {}
    storage.upsert_source(prices.source_id, "prices", "Yahoo Finance (yfinance)", YAHOO_URL,
                          "personal/research use only")
    end = now_utc.date()
    start = end - timedelta(days=cfg.price_history_days)
    symbols = active_symbols(cfg) + sorted(set(cfg.fx_pairs.values()))
    for sym, res in prices.fetch(symbols, start, end).items():
        if res.available:
            storage.upsert_prices(sym, res.bars, prices.source_id, now_utc)
        else:
            failed[f"ceny:{sym}"] = res.error or "brak danych"
    for feed in cfg.news.feeds:
        storage.upsert_source(f"rss:{feed.id}", "rss", feed.name, feed.url)
    items, errors = news.fetch(cfg.news.feeds, now_utc)
    storage.upsert_news(items)
    failed.update({f"rss:{k}": v for k, v in errors.items()})
    return failed


def build_evidence(cfg: Config, storage: Storage, cal: SessionCalendar, now_utc: datetime,
                   run_id: str, failed_sources: dict[str, str] | None = None) -> EvidencePackage:
    report_day = local_date(now_utc, cfg.app.timezone)
    source_id = "yfinance"
    since = now_utc.date() - timedelta(days=cfg.price_history_days)
    fx_cache = {cur: storage.load_prices(pair, source_id, since) for cur, pair in cfg.fx_pairs.items()}

    rows: list[InstrumentRow] = []
    excluded: list[tuple[str, str]] = []
    metrics_by_symbol: dict[str, analytics.Metrics] = {}
    pending: list[tuple[InstrumentRow, str | None]] = []
    for inst in cfg.instruments:
        if not inst.verified:
            continue
        elig = classify(inst, cfg.coverage)
        if elig.status in (Eligibility.EXCLUDED, Eligibility.REQUIRES_REVIEW):
            excluded.append((inst.symbol, elig.reason))
            continue
        expected = cal.last_completed_session(inst.exchange, now_utc)
        bars = storage.load_prices(inst.symbol, source_id, since)
        fx = fx_cache.get(inst.currency) if cfg.report.fx_reporting_currency else None
        if inst.currency == cfg.report.fx_reporting_currency:
            fx = None
        m = analytics.compute(bars, expected, fx if fx else None)
        metrics_by_symbol[inst.symbol] = m
        row = InstrumentRow(
            fact_id=f"{source_id}:{inst.symbol}:{m.last_session.isoformat() if m.last_session else 'na'}",
            symbol=inst.symbol, name=inst.name, kind=inst.kind, region=inst.region,
            currency=inst.currency, exchange=inst.exchange, is_regional_proxy=inst.is_regional_proxy,
            eligibility=elig.status.value, eligibility_reason=elig.reason, benchmark=inst.benchmark,
            metrics=m, rel_1d_vs_benchmark=None, source_id=source_id, source_url=YAHOO_URL,
        )
        pending.append((row, inst.benchmark))
    for row, bench in pending:
        rel = None
        if bench and bench in metrics_by_symbol:
            bm = metrics_by_symbol[bench]
            if bm.last_session == row.metrics.last_session:
                rel = analytics.relative(row.metrics.ret_1d, bm.ret_1d)
        if rel is not None:
            row = replace(row, rel_1d_vs_benchmark=rel)
        rows.append(row)

    regions: list[RegionStatus] = []
    for reg, exch in REGION_EXCHANGE.items():
        reg_rows = [r for r in rows if r.region == reg and r.eligibility == "eligible"]
        regions.append(RegionStatus(
            region=reg, exchange=exch,
            last_session=cal.last_completed_session(exch, now_utc),
            day_status=cal.day_status(exch, report_day),
            requested=len(reg_rows),
            received=sum(1 for r in reg_rows if r.metrics.last_session is not None),
        ))
    status, missing = decide_status(regions, cfg.coverage.required_regions,
                                    cfg.coverage.min_region_coverage)

    since_news = now_utc - timedelta(hours=cfg.news.lookback_hours)
    events = rank_events(group_events(storage.load_news(since_news)), now_utc,
                         cfg.news.lookback_hours, cfg.report.max_featured_events)
    sources = {YAHOO_URL: "Yahoo Finance (yfinance) — ceny i kursy FX"}
    for e in events:
        sources[e.url] = f"{e.source_name}: {e.title}"

    return EvidencePackage(
        report_date=report_day, generated_at_utc=now_utc, run_id=run_id,
        timezone=cfg.app.timezone,
        classification=f"{cfg.coverage.classification_provider} {cfg.coverage.classification_name}"
                       f" (as of: {cfg.coverage.classification_as_of or 'niezweryfikowane'}); bez PL i EM",
        regions=regions, rows=rows, excluded=excluded,
        unverified_symbols=[i.symbol for i in cfg.instruments if not i.verified],
        events=events, failed_sources=dict(sorted((failed_sources or {}).items())),
        sources=sources, content_status=status, missing_regions=missing,
    )


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def generate(cfg: Config, storage: Storage, cal: SessionCalendar, now_utc: datetime,
             llm: LLMProvider | None = None, failed_sources: dict[str, str] | None = None,
             force: bool = False) -> RunResult:
    started = datetime.now(UTC)
    run_id = uuid.uuid4().hex[:12]
    ev = build_evidence(cfg, storage, cal, now_utc, run_id, failed_sources)
    closes = {r.symbol: r.metrics.last_close for r in ev.rows}
    off = build_official(cfg, storage, now_utc, closes)
    ev.fundamentals, ev.filings, ev.macro = off.fundamentals, off.filings, off.macro
    for f in off.fundamentals:
        ev.sources[f.source_url] = f"SEC EDGAR — {f.ticker} (CIK {f.cik})"
    for fl in off.filings:
        ev.sources[fl["url"]] = f"SEC 8-K — {fl['ticker']} ({fl['filed']})"
    for m in off.macro:
        if m.value is not None:
            ev.sources[m.source_url] = f"FRED — {m.series_id}"
    ev.changes = compute_changes(
        storage.previous_snapshot(ev.report_date), ev,
        lambda sym, d: storage.close_on(sym, "yfinance", d))
    ev.upcoming = build_upcoming(cfg, storage, cal, ev.report_date)
    for u in ev.upcoming:
        ev.sources[u.source_url] = u.source_name + (
            " — kalendarz" if u.kind != "earnings" else " — daty wyników (szacunek)")
    fingerprint = ev.fingerprint()
    target = cfg.app.reports_dir / f"{ev.report_date.isoformat()}.md"
    if not force and storage.latest_fingerprint(ev.report_date) == fingerprint and target.exists():
        return RunResult(target, ev.content_status, "unchanged", skipped_unchanged=True)

    content = compose_with_fallback(llm or TemplateProvider(), ev)
    md = render(ev, content)
    problems = validate_markdown(md, ev)
    if problems:
        raise ReportQAError("; ".join(problems))
    write_atomic(target, md)
    storage.record_run(
        run_id=run_id, report_date=ev.report_date,
        version=storage.next_report_version(ev.report_date),
        content_status=ev.content_status, generation_mode=content.generation_mode,
        started_at_utc=started, finished_at_utc=datetime.now(UTC), config_hash=config_hash(cfg),
        input_fingerprint=fingerprint, report_path=str(target),
        report_sha256=hashlib.sha256(md.encode()).hexdigest(), evidence_json=ev.to_json(),
    )
    return RunResult(target, ev.content_status, content.generation_mode, skipped_unchanged=False)


@dataclass(frozen=True, slots=True)
class DeliverOutcome:
    status: str  # sent | already_sent | failed | no_report | disabled
    idempotency_key: str | None = None
    error_category: str | None = None


def _preview(md: str, status: str) -> str:
    """Plain-text e-mail body: session dates + TL;DR lines from the already-validated report."""
    lines = md.splitlines()
    sessions = next((ln.lstrip("> ").strip() for ln in lines if "Ostatnie zakończone sesje" in ln), "")
    tldr: list[str] = []
    in_tldr = False
    for ln in lines:
        if ln.startswith("## TL;DR"):
            in_tldr = True
            continue
        if in_tldr and ln.startswith("## "):
            break
        if in_tldr and ln[:2].rstrip(".").isdigit():
            tldr.append(ln.replace("**", ""))
    body = [f"Status raportu: {status}", sessions.replace("**", ""), "", "Najważniejsze:",
            *tldr[:3], "", "Pełny raport w załączniku (.md).",
            "Raport informacyjny, nie stanowi rekomendacji inwestycyjnej."]
    return "\n".join(body)


def deliver(cfg: Config, storage: Storage, report_date: date_t, mailer: Mailer,
            sender: str, recipient: str, now_utc: datetime) -> DeliverOutcome:
    """Send the latest report version for ``report_date`` once (idempotent per content)."""
    run = storage.latest_run(report_date)
    if not run or not Path(run["report_path"]).exists():
        return DeliverOutcome("no_report")
    key = f"{report_date.isoformat()}:{cfg.delivery.channel}:{run['report_sha256'][:16]}"
    if storage.delivery_status(key) == "sent":
        return DeliverOutcome("already_sent", key)
    path = Path(run["report_path"])
    status = run["content_status"].capitalize()
    if run["generation_mode"] == "template_fallback":
        status += " (fallback)"
    msg = build_message(
        path, sender=sender, recipient=recipient,
        subject=f"Market Digest | {report_date.isoformat()} | {status}",
        preview=_preview(path.read_text(encoding="utf-8"), status),
    )
    res = send_with_retry(mailer, msg, cfg.delivery.retries, cfg.delivery.retry_delay_seconds)
    storage.record_delivery(run_id=run["run_id"], channel=cfg.delivery.channel,
                            idempotency_key=key, status=res.status, delivery_id=res.delivery_id,
                            error_category=res.error_category, at_utc=now_utc)
    return DeliverOutcome(res.status, key, res.error_category)


def scheduled_moment(now_utc: datetime, cfg: Config, grace_hours: int = 12) -> datetime:
    """Snap a (possibly delayed) scheduled run to its intended slot, e.g. 23:30 Warsaw.

    GitHub schedules can start late; a run at 00:40 must still produce the previous day's
    report instead of shifting report_date by one day.
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(cfg.schedule.timezone)
    local = now_utc.astimezone(tz)
    slot_today = local.replace(hour=cfg.schedule.local_time.hour,
                               minute=cfg.schedule.local_time.minute, second=0, microsecond=0)
    if local >= slot_today:
        return slot_today.astimezone(UTC)
    slot_yesterday = (slot_today - timedelta(days=1)).replace(tzinfo=None).replace(tzinfo=tz)
    if local - slot_yesterday <= timedelta(hours=grace_hours):
        return slot_yesterday.astimezone(UTC)
    return now_utc


# --- Etap 3: SEC EDGAR + FRED -------------------------------------------------------------


@dataclass(slots=True)
class OfficialData:
    fundamentals: list[Fundamentals]
    filings: list[dict[str, str]]  # recent 8-K: ticker, filed, items, url
    macro: list[MacroRow]
    failed: dict[str, str]


def _fresh(storage: Storage, key: str, now_utc: datetime, hours: float) -> str | None:
    hit = storage.get_cache(key)
    if hit and now_utc - hit[1] < timedelta(hours=hours):
        return hit[0]
    return None


def fetch_official(cfg: Config, storage: Storage, sec: SecProvider | None,
                   fred: FredProvider | None, now_utc: datetime) -> dict[str, str]:
    """Refresh cached SEC/FRED payloads. Stale cache is kept on failure (with its date)."""
    failed: dict[str, str] = {}
    if sec is not None and cfg.fundamentals.enabled:
        try:
            tmap_raw = _fresh(storage, "sec:tickers", now_utc, 24 * 7)
            if tmap_raw is None:
                tmap = sec.ticker_map()
                storage.put_cache("sec:tickers", json.dumps(tmap), SEC_TICKERS_URL, now_utc)
            else:
                tmap = json.loads(tmap_raw)
            for inst in sec_eligible(cfg):
                cik = tmap.get(inst.symbol.upper())
                if cik is None:
                    failed[f"sec:{inst.symbol}"] = "brak CIK"
                    continue
                for kind, getter in (("facts", sec.company_facts), ("subs", sec.submissions)):
                    key = f"sec:{kind}:{cik}"
                    if _fresh(storage, key, now_utc, cfg.fundamentals.refresh_hours):
                        continue
                    try:
                        data = getter(cik)
                        if kind == "facts":
                            slim = [asdict(f) for f in parse_company_facts(data)]
                            payload = json.dumps(slim, default=str)
                        else:
                            payload = json.dumps(data.get("filings", {}).get("recent", {}))
                        storage.put_cache(key, payload, f"https://data.sec.gov/ CIK {cik}",
                                          now_utc)
                    except Exception as exc:
                        log.warning("SEC %s %s: %s", inst.symbol, kind, type(exc).__name__)
                        failed[f"sec:{inst.symbol}:{kind}"] = type(exc).__name__
        except Exception as exc:
            failed["sec"] = type(exc).__name__
    if fred is not None and cfg.macro.enabled:
        start = now_utc.date() - timedelta(days=cfg.macro.lookback_days)
        for s in cfg.macro.series:
            key = f"fred:{s.id}"
            if _fresh(storage, key, now_utc, cfg.macro.refresh_hours):
                continue
            try:
                obs = fred.series(s.id, start)
                if not obs:
                    raise ValueError("pusta seria")
                storage.upsert_macro(s.id, [(o.obs_date, o.value) for o in obs], now_utc)
                storage.put_cache(key, "ok", f"https://fred.stlouisfed.org/series/{s.id}", now_utc)
            except Exception as exc:
                log.warning("FRED %s: %s", s.id, type(exc).__name__)
                failed[f"fred:{s.id}"] = type(exc).__name__
    return failed


def sec_eligible(cfg: Config) -> list[InstrumentConfig]:
    """US issuers filing 10-Q/10-K. Foreign private issuers (20-F/IFRS) are out of scope."""
    return [i for i in cfg.instruments
            if i.kind == "equity" and i.issuer_country == "US" and i.verified]


def _facts_from_cache(payload: str) -> list[Fact]:
    out: list[Fact] = []
    for d in json.loads(payload):
        out.append(Fact(
            concept=d["concept"], unit=d["unit"],
            start=date_t.fromisoformat(d["start"]) if d["start"] else None,
            end=date_t.fromisoformat(d["end"]), val=float(d["val"]), fy=d.get("fy"),
            fp=d.get("fp"), form=d["form"], filed=date_t.fromisoformat(d["filed"]), accn=d["accn"],
        ))
    return out


ITEM_LABELS = {"2.02": "wyniki finansowe", "5.02": "zmiany w zarządzie/radzie",
               "1.01": "istotna umowa", "8.01": "inne zdarzenia", "7.01": "Reg FD",
               "2.01": "przejęcie/zbycie aktywów", "1.05": "incydent cyberbezpieczeństwa",
               "5.03": "zmiana statutu/regulaminu", "5.07": "głosowanie akcjonariuszy",
               "2.03": "nowe zobowiązanie finansowe", "3.02": "niezarejestrowana emisja akcji",
               "2.05": "koszty restrukturyzacji", "2.06": "odpisy z tytułu utraty wartości",
               "4.02": "nieaktualność wcześniejszych sprawozdań"}


def build_official(cfg: Config, storage: Storage, now_utc: datetime,
                   last_close: dict[str, float | None]) -> OfficialData:
    fundamentals: list[Fundamentals] = []
    filings: list[dict[str, str]] = []
    macro_rows: list[MacroRow] = []
    tmap_raw = storage.get_cache("sec:tickers")
    tmap: dict[str, int] = json.loads(tmap_raw[0]) if tmap_raw else {}
    since = now_utc.date() - timedelta(days=cfg.fundamentals.filings_lookback_days)
    if cfg.fundamentals.enabled:
        for inst in sec_eligible(cfg):
            cik = tmap.get(inst.symbol.upper())
            if cik is None:
                continue
            facts = storage.get_cache(f"sec:facts:{cik}")
            if facts:
                fundamentals.append(extract(inst.symbol, inst.name, cik,
                                            _facts_from_cache(facts[0]),
                                            last_close.get(inst.symbol)))
            subs = storage.get_cache(f"sec:subs:{cik}")
            if subs:
                for f in parse_recent_8k({"filings": {"recent": json.loads(subs[0])}}, cik, since):
                    items = [ITEM_LABELS.get(x.strip(), x.strip())
                             for x in f["items"].split(",") if x.strip() and x.strip() != "9.01"]
                    filings.append({**f, "ticker": inst.symbol,
                                    "items": ", ".join(items) or "bez opisu pozycji"})
    if cfg.macro.enabled:
        for s in cfg.macro.series:
            obs = [MacroObs(d, v) for d, v in storage.load_macro(s.id)]
            macro_rows.append(summarize(s.id, s.name, s.region, s.unit, s.transform, obs,
                                        now_utc.date()))
    filings.sort(key=lambda f: (f["filed"], f["ticker"]), reverse=True)
    return OfficialData(fundamentals, filings, macro_rows, {})


# --- Sekcja 10: kalendarz wydarzeń ---------------------------------------------------------


class UpcomingProvider(Protocol):
    def fomc_page(self) -> str: ...

    def ecb_page(self) -> str: ...

    def earnings_dates(self, symbol: str) -> list[date_t]: ...


def fetch_upcoming(cfg: Config, storage: Storage, prov: UpcomingProvider | None,
                   now_utc: datetime) -> dict[str, str]:
    failed: dict[str, str] = {}
    if prov is None or not cfg.upcoming.enabled:
        return failed
    hours = cfg.upcoming.refresh_hours
    if cfg.upcoming.central_banks:
        for key, getter, parser in (("cal:fomc", prov.fomc_page, parse_fomc),
                                    ("cal:ecb", prov.ecb_page, parse_ecb)):
            if _fresh(storage, key, now_utc, hours):
                continue
            try:
                evs = parser(getter())
                if not evs:
                    raise ValueError("nie znaleziono dat (zmiana struktury strony?)")
                storage.put_cache(key, json.dumps([asdict(e) for e in evs], default=str),
                                  evs[0].source_url, now_utc)
            except Exception as exc:
                log.warning("Kalendarz %s: %s", key, type(exc).__name__)
                failed[key.replace("cal:", "kalendarz:")] = type(exc).__name__
    if cfg.upcoming.earnings:
        for inst in cfg.instruments:
            if inst.kind != "equity" or not inst.verified:
                continue
            key = f"cal:earn:{inst.symbol}"
            if _fresh(storage, key, now_utc, hours):
                continue
            try:
                days = prov.earnings_dates(inst.symbol)
                evs = earnings_events(inst.symbol, inst.name, inst.region, days)
                storage.put_cache(key, json.dumps([asdict(e) for e in evs], default=str),
                                  f"https://finance.yahoo.com/quote/{inst.symbol}", now_utc)
            except Exception as exc:
                log.warning("Wyniki %s: %s", inst.symbol, type(exc).__name__)
                failed[f"kalendarz:wyniki:{inst.symbol}"] = type(exc).__name__
    return failed


def _events_from_cache(payload: str) -> list[UpcomingEvent]:
    return [UpcomingEvent(date_t.fromisoformat(d["day"]), d["title"], d["kind"], d["region"],
                          d["source_name"], d["source_url"], d["certainty"])
            for d in json.loads(payload)]


def build_upcoming(cfg: Config, storage: Storage, cal: SessionCalendar, report_day: date_t
                   ) -> list[UpcomingEvent]:
    if not cfg.upcoming.enabled:
        return []
    horizon = cfg.upcoming.horizon_days
    if report_day.weekday() == 6:
        horizon = max(horizon, cfg.upcoming.weekly_horizon_days)
    end = report_day + timedelta(days=horizon)
    evs: list[UpcomingEvent] = []
    keys = []
    if cfg.upcoming.central_banks:
        keys += ["cal:fomc", "cal:ecb"]
    if cfg.upcoming.earnings:
        keys += [f"cal:earn:{i.symbol}" for i in cfg.instruments
                 if i.kind == "equity" and i.verified]
    for key in keys:
        hit = storage.get_cache(key)
        if hit:
            evs.extend(_events_from_cache(hit[0]))
    if cfg.upcoming.market_closures:
        evs.extend(closures(cal.is_session, report_day, end))
    return within(evs, report_day, end)
