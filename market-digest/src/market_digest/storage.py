"""SQLite storage with versioned migrations and idempotent upserts. Timestamps in UTC."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path

from market_digest.models import NewsItem, PriceBar

MIGRATIONS: list[str] = [
    """
    CREATE TABLE sources (
        source_id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        base_url TEXT,
        license_note TEXT
    );
    CREATE TABLE instruments (
        symbol TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        region TEXT NOT NULL,
        currency TEXT NOT NULL,
        exchange TEXT NOT NULL,
        issuer_country TEXT,
        role TEXT NOT NULL,
        eligibility TEXT NOT NULL,
        eligibility_reason TEXT NOT NULL,
        classification_ref TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    );
    CREATE TABLE prices (
        symbol TEXT NOT NULL,
        session_date TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL,
        source_id TEXT NOT NULL REFERENCES sources(source_id),
        retrieved_at_utc TEXT NOT NULL,
        PRIMARY KEY (symbol, session_date, source_id)
    );
    CREATE TABLE news_items (
        news_id TEXT PRIMARY KEY,
        url_canonical TEXT NOT NULL UNIQUE,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        feed_id TEXT NOT NULL,
        source_name TEXT NOT NULL,
        tier TEXT NOT NULL,
        published_at_utc TEXT,
        retrieved_at_utc TEXT NOT NULL,
        injection_flag INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE report_runs (
        run_id TEXT PRIMARY KEY,
        report_date TEXT NOT NULL,
        version INTEGER NOT NULL,
        content_status TEXT NOT NULL,
        generation_mode TEXT NOT NULL,
        started_at_utc TEXT NOT NULL,
        finished_at_utc TEXT,
        config_hash TEXT NOT NULL,
        input_fingerprint TEXT,
        report_path TEXT,
        report_sha256 TEXT,
        UNIQUE (report_date, version)
    );
    CREATE TABLE report_snapshots (
        run_id TEXT PRIMARY KEY REFERENCES report_runs(run_id),
        evidence_json TEXT NOT NULL
    );
    CREATE TABLE delivery_attempts (
        attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES report_runs(run_id),
        channel TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL,
        delivery_id TEXT,
        last_attempt_at_utc TEXT,
        error_category TEXT
    );
    """,
]


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat() if dt else None


class Storage:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    def close(self) -> None:
        self.conn.close()

    def migrate(self) -> None:
        self.conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
        row = self.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        current = row[0] or 0
        for version, sql in enumerate(MIGRATIONS, start=1):
            if version > current:
                with self.conn:
                    self.conn.executescript(sql)
                    self.conn.execute("INSERT INTO schema_migrations VALUES (?)", (version,))

    def schema_version(self) -> int:
        return int(self.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])

    def upsert_source(self, source_id: str, kind: str, name: str, base_url: str | None,
                      license_note: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO sources VALUES (?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET "
                "kind=excluded.kind, name=excluded.name, base_url=excluded.base_url, "
                "license_note=excluded.license_note",
                (source_id, kind, name, base_url, license_note),
            )

    def upsert_instrument(self, *, symbol: str, name: str, kind: str, region: str, currency: str,
                          exchange: str, issuer_country: str | None, role: str, eligibility: str,
                          eligibility_reason: str, classification_ref: str, now_utc: datetime) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO instruments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (symbol, name, kind, region, currency, exchange, issuer_country, role,
                 eligibility, eligibility_reason, classification_ref, _iso(now_utc)),
            )

    def upsert_prices(self, symbol: str, bars: Iterable[PriceBar], source_id: str,
                      retrieved_at_utc: datetime) -> int:
        rows = [
            (symbol, b.session_date.isoformat(), b.open, b.high, b.low, b.close, b.adj_close,
             b.volume, source_id, _iso(retrieved_at_utc))
            for b in bars
        ]
        with self.conn:
            self.conn.executemany(
                "INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(symbol, session_date, source_id) DO UPDATE SET "
                "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, "
                "adj_close=excluded.adj_close, volume=excluded.volume, "
                "retrieved_at_utc=excluded.retrieved_at_utc",
                rows,
            )
        return len(rows)

    def load_prices(self, symbol: str, source_id: str, since: date | None = None) -> list[PriceBar]:
        q = ("SELECT session_date, open, high, low, close, adj_close, volume FROM prices "
             "WHERE symbol=? AND source_id=?")
        args: list[object] = [symbol, source_id]
        if since:
            q += " AND session_date>=?"
            args.append(since.isoformat())
        q += " ORDER BY session_date"
        return [
            PriceBar(session_date=date.fromisoformat(r[0]), open=r[1], high=r[2], low=r[3],
                     close=r[4], adj_close=r[5], volume=r[6])
            for r in self.conn.execute(q, args)
        ]

    def upsert_news(self, items: Iterable[NewsItem]) -> int:
        import hashlib

        count = 0
        with self.conn:
            for it in items:
                news_id = hashlib.sha256(it.url_canonical.encode()).hexdigest()[:16]
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO news_items VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (news_id, it.url_canonical, it.url, it.title, it.summary, it.feed_id,
                     it.source_name, it.tier, _iso(it.published_at_utc),
                     _iso(it.retrieved_at_utc), int(it.injection_flag)),
                )
                count += cur.rowcount
        return count

    def load_news(self, since_utc: datetime) -> list[NewsItem]:
        rows = self.conn.execute(
            "SELECT feed_id, source_name, tier, title, url, url_canonical, published_at_utc, "
            "retrieved_at_utc, summary, injection_flag FROM news_items "
            "WHERE published_at_utc >= ? ORDER BY published_at_utc",
            (_iso(since_utc),),
        ).fetchall()
        return [
            NewsItem(feed_id=r[0], source_name=r[1], tier=r[2], title=r[3], url=r[4],
                     url_canonical=r[5],
                     published_at_utc=datetime.fromisoformat(r[6]) if r[6] else None,
                     retrieved_at_utc=datetime.fromisoformat(r[7]), summary=r[8],
                     injection_flag=bool(r[9]))
            for r in rows
        ]

    def next_report_version(self, report_date: date) -> int:
        row = self.conn.execute(
            "SELECT MAX(version) FROM report_runs WHERE report_date=?", (report_date.isoformat(),)
        ).fetchone()
        return int(row[0] or 0) + 1

    def record_run(self, *, run_id: str, report_date: date, version: int, content_status: str,
                   generation_mode: str, started_at_utc: datetime, finished_at_utc: datetime,
                   config_hash: str, input_fingerprint: str, report_path: str,
                   report_sha256: str, evidence_json: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO report_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, report_date.isoformat(), version, content_status, generation_mode,
                 _iso(started_at_utc), _iso(finished_at_utc), config_hash, input_fingerprint,
                 report_path, report_sha256),
            )
            self.conn.execute("INSERT INTO report_snapshots VALUES (?,?)", (run_id, evidence_json))

    def latest_fingerprint(self, report_date: date) -> str | None:
        row = self.conn.execute(
            "SELECT input_fingerprint FROM report_runs WHERE report_date=? "
            "ORDER BY version DESC LIMIT 1",
            (report_date.isoformat(),),
        ).fetchone()
        return str(row[0]) if row and row[0] else None
