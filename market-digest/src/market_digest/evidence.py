"""Evidence package: the only input allowed for the narrative layer (template or LLM)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from market_digest.analytics import Metrics
from market_digest.calendar import DayStatus
from market_digest.models import NewsEvent

REGION_LABELS = {
    "us": "USA",
    "developed_europe": "Europa rozwinięta",
    "developed_asia": "Japonia / Azja rozwinięta",
    "other_developed": "Kanada / Australia",
    "global": "Globalne",
}


@dataclass(frozen=True, slots=True)
class InstrumentRow:
    fact_id: str
    symbol: str
    name: str
    kind: str
    region: str
    currency: str
    exchange: str
    is_regional_proxy: bool
    eligibility: str
    eligibility_reason: str
    benchmark: str | None
    metrics: Metrics
    rel_1d_vs_benchmark: float | None
    source_id: str
    source_url: str


@dataclass(frozen=True, slots=True)
class RegionStatus:
    region: str
    exchange: str
    last_session: date | None
    day_status: DayStatus
    requested: int
    received: int

    @property
    def coverage(self) -> float:
        return self.received / self.requested if self.requested else 0.0


@dataclass(slots=True)
class EvidencePackage:
    report_date: date
    generated_at_utc: datetime
    run_id: str
    timezone: str
    classification: str
    regions: list[RegionStatus]
    rows: list[InstrumentRow]
    excluded: list[tuple[str, str]]
    unverified_symbols: list[str]
    events: list[NewsEvent]
    failed_sources: dict[str, str]
    sources: dict[str, str] = field(default_factory=dict)  # url allowlist: url -> label
    content_status: str = "complete"
    missing_regions: list[str] = field(default_factory=list)

    def allowed_urls(self) -> set[str]:
        return set(self.sources)

    def to_json(self) -> str:
        return json.dumps(_plain(asdict(self)), ensure_ascii=False, sort_keys=True, indent=1)

    def fingerprint(self) -> str:
        """Hash of report-relevant inputs only (stable across re-fetches of identical data)."""
        data = {
            "report_date": self.report_date.isoformat(),
            "rows": _plain([asdict(r) for r in self.rows]),
            "regions": _plain([asdict(r) for r in self.regions]),
            "events": sorted(e.event_id for e in self.events),
            "failed": sorted(self.failed_sources),
            "excluded": _plain(self.excluded),
            "status": self.content_status,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


def _plain(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_plain(v) for v in obj]
    if isinstance(obj, date | datetime):
        return obj.isoformat()
    if isinstance(obj, set | frozenset):
        return sorted(_plain(v) for v in obj)
    return obj


def decide_status(regions: list[RegionStatus], required: tuple[str, ...],
                  min_coverage: float) -> tuple[str, list[str]]:
    """'partial' if any required region lacks data. A scheduled holiday is not missing data."""
    missing: list[str] = []
    by_region = {r.region: r for r in regions}
    for reg in required:
        st = by_region.get(reg)
        if st is None or st.received == 0 or st.coverage < min_coverage:
            missing.append(reg)
    return ("partial" if missing else "complete"), missing
