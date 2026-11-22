"""News deduplication, event grouping and deterministic ranking."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import datetime, timedelta

from market_digest.models import NewsEvent, NewsItem

_WORD = re.compile(r"[a-z0-9ąćęłńóśźż]+", re.I)
_STOP = frozenset({
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for",
    "with", "by", "at", "from", "is", "are", "as", "its", "new",
})
TIER_WEIGHT = {"official": 3.0, "specialist": 2.0, "media": 1.5}
SIMILARITY_THRESHOLD = 0.6


def _tokens(title: str) -> frozenset[str]:
    return frozenset(w.lower() for w in _WORD.findall(title) if w.lower() not in _STOP and len(w) > 2)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
    seen: dict[str, NewsItem] = {}
    for it in items:
        if it.url_canonical not in seen:
            seen[it.url_canonical] = it
    return list(seen.values())


def group_events(items: Iterable[NewsItem]) -> list[NewsEvent]:
    """Group near-duplicate titles (reposts) into a single event with one primary source."""
    ordered = sorted(
        dedupe(items),
        key=lambda i: (-TIER_WEIGHT.get(i.tier, 1.0),
                       i.published_at_utc.timestamp() if i.published_at_utc else 0.0,
                       i.url_canonical),
    )
    events: list[tuple[frozenset[str], NewsEvent]] = []
    for it in ordered:
        toks = _tokens(it.title)
        for etoks, ev in events:
            if _jaccard(toks, etoks) >= SIMILARITY_THRESHOLD:
                ev.items.append(it)
                break
        else:
            eid = hashlib.sha256(it.url_canonical.encode()).hexdigest()[:12]
            events.append((toks, NewsEvent(eid, it.title, it.url, it.source_name, it.tier,
                                           it.published_at_utc, it.summary, [it])))
    return [ev for _, ev in events]


def rank_events(events: list[NewsEvent], now_utc: datetime, lookback_hours: int,
                limit: int) -> list[NewsEvent]:
    cutoff = now_utc - timedelta(hours=lookback_hours)
    kept: list[NewsEvent] = []
    for ev in events:
        if any(i.injection_flag for i in ev.items):
            continue
        if ev.published_at_utc is None or ev.published_at_utc < cutoff or ev.published_at_utc > now_utc:
            continue
        age_h = (now_utc - ev.published_at_utc).total_seconds() / 3600
        recency = max(0.0, 1.0 - age_h / lookback_hours)
        sources = len({i.feed_id for i in ev.items})
        ev.score = round(TIER_WEIGHT.get(ev.tier, 1.0) + 2.0 * recency + 0.5 * (sources - 1), 6)
        kept.append(ev)
    kept.sort(key=lambda e: (-e.score, e.event_id))
    return kept[:limit]
