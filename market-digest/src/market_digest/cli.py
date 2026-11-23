"""Command line interface: fetch, report, run, doctor."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import typer

from market_digest import pipeline
from market_digest.calendar import ExchangeCalendars, local_date
from market_digest.config import Config, load_config
from market_digest.delivery import DeliveryConfigError, SmtpMailer, SmtpSettings
from market_digest.eligibility import classify
from market_digest.providers.news import RssProvider
from market_digest.providers.official import HttpFred, HttpSec, HttpUpcoming
from market_digest.providers.prices import YFinanceProvider
from market_digest.storage import Storage

app = typer.Typer(add_completion=False, help="Market Digest — codzienny raport rynkowy (MD, PL).")
ConfigOpt = typer.Option(Path("config.yaml"), "--config", "-c", help="Plik konfiguracji YAML")
AtOpt = typer.Option(None, "--at", help="Moment raportu w ISO 8601 z offsetem (domyślnie teraz)")


def _setup(config: Path) -> tuple[Config, Storage]:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config(config)
    return cfg, Storage(cfg.app.db_path)


def _now(at: str | None) -> datetime:
    if not at:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(at)
    if dt.tzinfo is None:
        raise typer.BadParameter("--at wymaga strefy czasowej, np. 2026-11-23T23:30+01:00")
    return dt.astimezone(UTC)


def _official_fetch(cfg: Config, st: Storage, now: datetime) -> dict[str, str]:
    import os

    sec = None
    ua = os.environ.get(cfg.fundamentals.user_agent_env, "").strip()
    if cfg.fundamentals.enabled:
        if "@" in ua:
            sec = HttpSec(ua)
        else:
            typer.echo(f"SEC pominięte: ustaw {cfg.fundamentals.user_agent_env} "
                       "(np. 'market-digest twoj@email')", err=True)
    fred = HttpFred() if cfg.macro.enabled else None
    failed = pipeline.fetch_official(cfg, st, sec, fred, now)
    failed.update(pipeline.fetch_upcoming(cfg, st, HttpUpcoming(), now))
    if sec is None and cfg.fundamentals.enabled:
        failed["sec"] = "brak SEC_USER_AGENT"
    return failed


@app.command()
def fetch(config: Path = ConfigOpt, at: str | None = AtOpt) -> None:
    """Pobierz ceny, RSS, SEC i FRED do SQLite."""
    cfg, st = _setup(config)
    now = _now(at)
    failed = pipeline.fetch(cfg, st, YFinanceProvider(), RssProvider(cfg.news.timeout_seconds,
                            cfg.news.max_items_per_feed), now)
    failed.update(_official_fetch(cfg, st, now))
    typer.echo(f"Pobrano. Niedostępne źródła: {failed or 'brak'}")


@app.command()
def report(config: Path = ConfigOpt, at: str | None = AtOpt,
           force: bool = typer.Option(False, help="Wygeneruj nową wersję mimo braku zmian")) -> None:
    """Wygeneruj raport z danych w SQLite (offline)."""
    cfg, st = _setup(config)
    res = pipeline.generate(cfg, st, ExchangeCalendars(), _now(at), force=force)
    _print(res)


@app.command()
def run(config: Path = ConfigOpt, at: str | None = AtOpt,
        force: bool = typer.Option(False, help="Wygeneruj nową wersję mimo braku zmian"),
        send: bool = typer.Option(False, "--send", help="Wyślij raport e-mailem po wygenerowaniu"),
        scheduled: bool = typer.Option(False, "--scheduled",
                                       help="Opóźniony start harmonogramu = slot 23:30 (nie zmienia daty)")
        ) -> None:
    """Pełny przebieg: fetch + report (+ opcjonalnie wysyłka)."""
    cfg, st = _setup(config)
    now = _now(at)
    if scheduled:
        now = pipeline.scheduled_moment(now, cfg)
    failed = pipeline.fetch(cfg, st, YFinanceProvider(), RssProvider(cfg.news.timeout_seconds,
                            cfg.news.max_items_per_feed), now)
    failed.update(_official_fetch(cfg, st, now))
    res = pipeline.generate(cfg, st, ExchangeCalendars(), now, failed_sources=failed, force=force)
    _print(res)
    if send:
        _deliver(cfg, st, now)


@app.command()
def deliver(config: Path = ConfigOpt, at: str | None = AtOpt,
            report_date: str | None = typer.Option(None, "--date",
                                                   help="Data raportu YYYY-MM-DD"),
            scheduled: bool = typer.Option(False, "--scheduled",
                                           help="Data raportu wg slotu harmonogramu")) -> None:
    """Wyślij (lub ponów wysyłkę) istniejącego raportu bez ponownego generowania."""
    cfg, st = _setup(config)
    now = _now(at)
    if scheduled:
        now = pipeline.scheduled_moment(now, cfg)
    _deliver(cfg, st, now, date.fromisoformat(report_date) if report_date else None)


def _deliver(cfg: Config, st: Storage, now: datetime, day: date | None = None) -> None:
    try:
        smtp = SmtpSettings.from_env(cfg.delivery)
    except DeliveryConfigError as exc:
        typer.echo(f"Wysyłka niemożliwa: {exc}", err=True)
        raise typer.Exit(2) from exc
    day = day or local_date(now, cfg.app.timezone)
    out = pipeline.deliver(cfg, st, day, SmtpMailer(smtp, cfg.delivery.timeout_seconds),
                           smtp.username, smtp.recipient, now)
    typer.echo(f"Dostarczenie {day.isoformat()}: {out.status}"
               + (f" ({out.error_category})" if out.error_category else ""))
    if out.status in ("failed", "no_report"):
        raise typer.Exit(1)


@app.command()
def heartbeat(config: Path = ConfigOpt, at: str | None = AtOpt,
              max_age_hours: float = typer.Option(26.0, help="Maks. wiek ostatniej wysyłki")
              ) -> None:
    """Zwraca kod 1, jeśli od ostatniej udanej wysyłki minęło za dużo czasu."""
    _, st = _setup(config)
    last = st.last_successful_delivery()
    now = _now(at)
    if last is None or now - last > timedelta(hours=max_age_hours):
        typer.echo(f"ALERT: ostatnia udana wysyłka: {last.isoformat() if last else 'nigdy'}")
        raise typer.Exit(1)
    typer.echo(f"OK: ostatnia udana wysyłka {last.isoformat()}")


def _print(res: pipeline.RunResult) -> None:
    if res.skipped_unchanged:
        typer.echo(f"Bez zmian względem ostatniej wersji: {res.report_path}")
    else:
        typer.echo(f"Raport: {res.report_path} (treść: {res.content_status}, "
                   f"tryb: {res.generation_mode})")


@app.command()
def doctor(config: Path = ConfigOpt) -> None:
    """Sprawdź konfigurację, kwalifikację instrumentów i dostępność symboli u dostawcy."""
    cfg, st = _setup(config)
    typer.echo(f"Konfiguracja OK; schemat DB v{st.schema_version()}")
    for inst in cfg.instruments:
        r = classify(inst, cfg.coverage)
        typer.echo(f"  {inst.symbol:10} {r.status.value:16} {r.reason}"
                   + ("" if inst.verified else "  [verified=false]"))
    end = datetime.now(UTC).date()
    symbols = [i.symbol for i in cfg.instruments] + sorted(set(cfg.fx_pairs.values()))
    results = YFinanceProvider().fetch(symbols, end - timedelta(days=10), end)
    typer.echo("Dostępność symboli (yfinance, ostatnie 10 dni):")
    for sym, res in results.items():
        last = res.bars[-1].session_date.isoformat() if res.bars else "-"
        typer.echo(f"  {sym:10} {'OK' if res.available else 'BRAK':5} ostatnia sesja: {last}")
    typer.echo("Uwaga: OK oznacza tylko, że symbol zwraca dane. Zanim ustawisz verified: true, "
               "sprawdź, czy instrument jest właściwy (nazwa, waluta).")


if __name__ == "__main__":
    app()
