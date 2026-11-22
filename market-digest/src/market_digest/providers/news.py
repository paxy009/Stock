"""RSS ingestion. All fetched text is untrusted data: sanitized, never executed as instructions."""

from __future__ import annotations

import html
import logging
import re
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from market_digest.config import FeedConfig
from market_digest.models import NewsItem

log = logging.getLogger(__name__)

_TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|cmpid$)", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior) (instructions|prompts)|zignoruj (wszystkie )?"
    r"(poprzednie|wcześniejsze) (polecenia|instrukcje)|system prompt|you are now|"
    r"jesteś teraz|disregard the above)",
    re.I,
)


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not _TRACKING.match(k)]
    host = parts.netloc.lower()
    host = host.removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https" if parts.scheme in ("http", "https") else parts.scheme,
                       host, path, urlencode(sorted(query)), ""))


def safe_url(url: str) -> bool:
    return urlsplit(url).scheme in ("http", "https")


def clean_text(raw: str, limit: int = 400) -> str:
    text = html.unescape(_TAG.sub(" ", raw or ""))
    text = _WS.sub(" ", text).strip()
    # Neutralize markdown/HTML control characters in untrusted text
    text = text.replace("<", "‹").replace(">", "›").replace("[", "(").replace("]", ")")
    text = text.replace("`", "'").replace("|", "/").replace("{", "(").replace("}", ")")
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def looks_like_injection(*texts: str) -> bool:
    return any(_INJECTION.search(t or "") for t in texts)


def _published(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            y, mo, d, h, mi, s = (int(x) for x in st[:6])
            return datetime(y, mo, d, h, mi, s, tzinfo=UTC)
    return None


def parse_feed(feed: FeedConfig, content: bytes, retrieved_at: datetime,
               max_items: int = 40) -> list[NewsItem]:
    import feedparser

    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"niepoprawny feed: {parsed.get('bozo_exception')}")
    items: list[NewsItem] = []
    for entry in parsed.entries[:max_items]:
        link = str(entry.get("link") or "").strip()
        title_raw = str(entry.get("title") or "")
        summary_raw = str(entry.get("summary") or "")
        if not link or not safe_url(link) or not title_raw.strip():
            continue
        items.append(
            NewsItem(
                feed_id=feed.id,
                source_name=feed.name,
                tier=feed.tier,
                title=clean_text(title_raw, 200),
                url=link,
                url_canonical=canonical_url(link),
                published_at_utc=_published(entry),
                retrieved_at_utc=retrieved_at,
                summary=clean_text(summary_raw, 300),
                injection_flag=looks_like_injection(title_raw, summary_raw),
            )
        )
    return items


class NewsProvider(Protocol):
    def fetch(self, feeds: tuple[FeedConfig, ...], now_utc: datetime) -> tuple[list[NewsItem], dict[str, str]]: ...


class RssProvider:
    def __init__(self, timeout: float = 15.0, max_items: int = 40) -> None:
        self.timeout = timeout
        self.max_items = max_items

    def fetch(self, feeds: tuple[FeedConfig, ...], now_utc: datetime) -> tuple[list[NewsItem], dict[str, str]]:
        import httpx

        items: list[NewsItem] = []
        errors: dict[str, str] = {}
        headers = {"User-Agent": "market-digest/0.1 (private research digest)"}
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            for feed in feeds:
                try:
                    resp = client.get(feed.url)
                    resp.raise_for_status()
                    items.extend(parse_feed(feed, resp.content, now_utc, self.max_items))
                except Exception as exc:  # isolate failures per feed
                    log.warning("RSS %s: %s", feed.id, exc)
                    errors[feed.id] = type(exc).__name__
        return items, errors


class StaticNewsProvider:
    def __init__(self, items: list[NewsItem], errors: dict[str, str] | None = None) -> None:
        self.items = items
        self.errors = errors or {}

    def fetch(self, feeds: tuple[FeedConfig, ...], now_utc: datetime) -> tuple[list[NewsItem], dict[str, str]]:
        return list(self.items), dict(self.errors)
