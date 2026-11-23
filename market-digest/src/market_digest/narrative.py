"""Narrative providers. LLMs may only reference evidence; numbers come from Python tables."""

from __future__ import annotations

import logging
from typing import Protocol

from market_digest.evidence import REGION_LABELS, EvidencePackage
from market_digest.models import ReportContent, TldrItem

log = logging.getLogger(__name__)


class LLMProvider(Protocol):
    name: str

    def compose(self, evidence: EvidencePackage) -> ReportContent: ...


def _fmt(v: float | None) -> str:
    return "brak danych" if v is None else f"{v:+.2f}%".replace(".", ",")


class TemplateProvider:
    """Deterministic, model-free narrative built only from the evidence package."""

    name = "template"

    def compose(self, evidence: EvidencePackage) -> ReportContent:
        tldr: list[TldrItem] = []
        for ev in evidence.events[:3]:
            tldr.append(TldrItem(f"**{ev.title}** ({ev.source_name})", ev.url, ev.source_name))

        by_region: dict[str, list[str]] = {}
        for row in evidence.rows:
            if (row.eligibility != "eligible" or row.kind not in ("etf", "index")
                    or row.sector is not None):
                continue
            if row.metrics.ret_1d is None:
                continue
            by_region.setdefault(row.region, []).append(f"{row.symbol} {_fmt(row.metrics.ret_1d)}")
        for reg in ("us", "developed_europe", "developed_asia", "other_developed"):
            if len(tldr) >= 5:
                break
            if reg in by_region:
                last = next((r.last_session for r in evidence.regions if r.region == reg), None)
                when = last.isoformat() if last else "brak daty"
                tldr.append(TldrItem(
                    f"**{REGION_LABELS[reg]}** (ostatnia sesja {when}): "
                    + ", ".join(by_region[reg][:3])
                    + " — ruch 1 sesji; przyczyna nieustalona w danych wejściowych."
                ))
        if not tldr:
            tldr.append(TldrItem("Brak nowych zweryfikowanych danych i wiadomości w tym oknie."))

        overview = (
            "Podsumowanie wygenerowane szablonem na podstawie metryk policzonych w Pythonie. "
            "Ruchy cen podano bez przypisywania przyczyn — brak potwierdzonego związku "
            "przyczynowego w danych wejściowych."
        )
        if evidence.missing_regions:
            overview += " Brak pełnych danych dla: " + ", ".join(
                REGION_LABELS.get(r, r) for r in evidence.missing_regions) + "."
        return ReportContent(generation_mode="template", tldr=tuple(tldr), overview=overview)


def compose_with_fallback(primary: LLMProvider, evidence: EvidencePackage) -> ReportContent:
    """Use the primary provider; on error or invalid citations fall back to the template."""
    from market_digest.qa import validate_content

    if isinstance(primary, TemplateProvider):
        return primary.compose(evidence)
    try:
        content = primary.compose(evidence)
        problems = validate_content(content, evidence)
        if problems:
            raise ValueError("; ".join(problems))
        return content
    except Exception as exc:
        log.warning("LLM %s niedostępny/odrzucony: %s", primary.name, exc)
        fb = TemplateProvider().compose(evidence)
        return ReportContent("template_fallback", fb.tldr, fb.overview,
                             fallback_reason=f"{primary.name}: {type(exc).__name__}")
