"""SEC EDGAR and FRED adapters. Failures are isolated and reported, never fatal."""

from __future__ import annotations

import csv
import io
import logging
import time
from datetime import date
from typing import Any, Protocol

from market_digest.fundamentals import ALL_CONCEPTS, Fact
from market_digest.macro import MacroObs

log = logging.getLogger(__name__)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"


def parse_ticker_map(data: dict[str, Any]) -> dict[str, int]:
    return {str(v["ticker"]).upper(): int(v["cik_str"]) for v in data.values()}


def parse_company_facts(data: dict[str, Any]) -> list[Fact]:
    facts: list[Fact] = []
    gaap = data.get("facts", {}).get("us-gaap", {})
    for concept in ALL_CONCEPTS:
        units = gaap.get(concept, {}).get("units", {})
        for unit, rows in units.items():
            if unit not in ("USD", "USD/shares"):
                continue
            for r in rows:
                if r.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
                    continue
                try:
                    facts.append(Fact(
                        concept=concept, unit=unit,
                        start=date.fromisoformat(r["start"]) if r.get("start") else None,
                        end=date.fromisoformat(r["end"]), val=float(r["val"]),
                        fy=r.get("fy"), fp=r.get("fp"), form=r["form"],
                        filed=date.fromisoformat(r["filed"]), accn=r["accn"],
                    ))
                except (KeyError, ValueError, TypeError):
                    continue
    return facts


def parse_recent_8k(data: dict[str, Any], cik: int, since: date) -> list[dict[str, str]]:
    rec = data.get("filings", {}).get("recent", {})
    out: list[dict[str, str]] = []
    for i, form in enumerate(rec.get("form", [])):
        if form != "8-K":
            continue
        filed = date.fromisoformat(rec["filingDate"][i])
        if filed < since:
            continue
        accn = rec["accessionNumber"][i]
        doc = rec["primaryDocument"][i]
        url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
               f"{accn.replace('-', '')}/{doc}")
        out.append({"filed": filed.isoformat(), "items": rec.get("items", [""] * (i + 1))[i],
                    "url": url})
    return out


def parse_fred_csv(text: str) -> list[MacroObs]:
    out: list[MacroObs] = []
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for row in reader:
        if len(row) < 2 or row[1] in ("", "."):
            continue
        try:
            out.append(MacroObs(date.fromisoformat(row[0]), float(row[1])))
        except ValueError:
            continue
    return out


class SecProvider(Protocol):
    def ticker_map(self) -> dict[str, int]: ...

    def company_facts(self, cik: int) -> dict[str, Any]: ...

    def submissions(self, cik: int) -> dict[str, Any]: ...


class FredProvider(Protocol):
    def series(self, series_id: str, start: date) -> list[MacroObs]: ...


class HttpSec:
    """Respects SEC fair access: declared User-Agent and <10 req/s."""

    def __init__(self, user_agent: str, timeout: float = 30.0, min_interval: float = 0.2) -> None:
        if "@" not in user_agent:
            raise ValueError("SEC wymaga User-Agent z adresem kontaktowym")
        self.headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self.timeout = timeout
        self.min_interval = min_interval
        self._last = 0.0

    def _get(self, url: str) -> dict[str, Any]:
        import httpx

        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        resp = httpx.get(url, headers=self.headers, timeout=self.timeout, follow_redirects=True)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def ticker_map(self) -> dict[str, int]:
        return parse_ticker_map(self._get(SEC_TICKERS_URL))

    def company_facts(self, cik: int) -> dict[str, Any]:
        return self._get(SEC_FACTS_URL.format(cik=cik))

    def submissions(self, cik: int) -> dict[str, Any]:
        return self._get(SEC_SUBMISSIONS_URL.format(cik=cik))


class HttpFred:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def series(self, series_id: str, start: date) -> list[MacroObs]:
        import httpx

        url = FRED_CSV_URL.format(sid=series_id, start=start.isoformat())
        resp = httpx.get(url, timeout=self.timeout, follow_redirects=True,
                         headers={"User-Agent": "market-digest/0.1"})
        resp.raise_for_status()
        return parse_fred_csv(resp.text)


class HttpUpcoming:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.headers = {"User-Agent": "market-digest/0.1 (private research digest)"}

    def _text(self, url: str) -> str:
        import httpx

        resp = httpx.get(url, timeout=self.timeout, headers=self.headers, follow_redirects=True)
        resp.raise_for_status()
        return resp.text

    def fomc_page(self) -> str:
        from market_digest.upcoming import FOMC_URL

        return self._text(FOMC_URL)

    def ecb_page(self) -> str:
        from market_digest.upcoming import ECB_URL

        return self._text(ECB_URL)

    def earnings_dates(self, symbol: str) -> list[date]:
        import yfinance as yf

        from market_digest.upcoming import parse_earnings_calendar

        return parse_earnings_calendar(yf.Ticker(symbol).calendar)
