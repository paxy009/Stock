"""Command line interface: fetch, report, run, doctor."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer

from market_digest import pipeline
from market_digest.calendar import ExchangeCalendars
from market_digest.config import Config, load_config
from market_digest.eligibility import classify
from market_digest.providers.news import RssProvider
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


@app.command()
def fetch(config: Path = ConfigOpt, at: str | None = AtOpt) -> None:
    """Pobierz ceny i RSS do SQLite."""
    cfg, st = _setup(config)
    failed = pipeline.fetch(cfg, st, YFinanceProvider(), RssProvider(cfg.news.timeout_seconds,
                            cfg.news.max_items_per_feed), _now(at))
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
        force: bool = typer.Option(False, help="Wygeneruj nową wersję mimo braku zmian")) -> None:
    """Pełny przebieg: fetch + report."""
    cfg, st = _setup(config)
    now = _now(at)
    failed = pipeline.fetch(cfg, st, YFinanceProvider(), RssProvider(cfg.news.timeout_seconds,
                            cfg.news.max_items_per_feed), now)
    res = pipeline.generate(cfg, st, ExchangeCalendars(), now, failed_sources=failed, force=force)
    _print(res)


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
