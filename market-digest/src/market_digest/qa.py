"""Report QA: block placeholders, non-allowlisted URLs and unsafe content before publishing."""

from __future__ import annotations

import re

from market_digest.evidence import EvidencePackage
from market_digest.models import ReportContent

_LINK = re.compile(r"\]\((?P<url>[^)\s]+)\)")
_PLACEHOLDER = re.compile(r"\{\{|\}\}|example\.(org|com)|lorem ipsum", re.I)
_HTML = re.compile(r"<\s*(script|iframe|img|a|style)\b", re.I)


def validate_content(content: ReportContent, evidence: EvidencePackage) -> list[str]:
    allowed = evidence.allowed_urls()
    problems = []
    for item in content.tldr:
        if item.url and item.url not in allowed:
            problems.append(f"URL spoza snapshotu: {item.url}")
    return problems


def validate_markdown(md: str, evidence: EvidencePackage) -> list[str]:
    problems: list[str] = []
    if _PLACEHOLDER.search(md):
        problems.append("placeholder w raporcie")
    if _HTML.search(md):
        problems.append("niedozwolony HTML")
    allowed = evidence.allowed_urls()
    for m in _LINK.finditer(md):
        url = m.group("url")
        if url.startswith("#"):
            continue
        if not url.startswith(("https://", "http://")):
            problems.append(f"niebezpieczny schemat URL: {url}")
        elif url not in allowed:
            problems.append(f"URL spoza snapshotu: {url}")
    return problems
