"""Orchestrates fetch -> store -> analyze -> evidence -> narrative -> render -> QA -> atomic write."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from datetime import date as date_t
from pathlib import Path

from market_digest import analytics
from market_digest.calendar import SessionCalendar, local_date
from market_digest.config import Config
from market_digest.delivery import Mailer, build_message, send_with_retry
from market_digest.eligibility import classify
from market_digest.events import group_events, rank_events
from market_digest.evidence import EvidencePackage, InstrumentRow, RegionStatus, decide_status
from market_digest.models import Eligibility
from market_digest.narrative import LLMProvider, TemplateProvider, compose_with_fallback
from market_digest.providers.news import NewsProvider
from market_digest.providers.prices import PriceProvider
from market_digest.qa import validate_markdown
from market_digest.renderer import render
from market_digest.storage import Storage

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
