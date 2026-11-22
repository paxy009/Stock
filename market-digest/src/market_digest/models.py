"""Domain models shared across modules. ``None`` always means "no data", never 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class Eligibility(StrEnum):
    ELIGIBLE = "eligible"
    BENCHMARK_ONLY = "benchmark_only"
    REQUIRES_REVIEW = "requires_review"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class PriceBar:
    session_date: date
    close: float | None
    adj_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None


@dataclass(frozen=True, slots=True)
class NewsItem:
    feed_id: str
    source_name: str
    tier: str
    title: str
    url: str
    url_canonical: str
    published_at_utc: datetime | None
    retrieved_at_utc: datetime
    summary: str = ""
    injection_flag: bool = False


@dataclass(slots=True)
class NewsEvent:
    event_id: str
    title: str
    url: str
    source_name: str
    tier: str
    published_at_utc: datetime | None
    summary: str
    items: list[NewsItem] = field(default_factory=list)
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class TldrItem:
    text: str
    url: str | None = None
    url_label: str = "źródło"


@dataclass(frozen=True, slots=True)
class ReportContent:
    """Narrative part of the report. Numbers in tables never come from here."""

    generation_mode: str  # llm | template | template_fallback
    tldr: tuple[TldrItem, ...]
    overview: str
    fallback_reason: str | None = None
