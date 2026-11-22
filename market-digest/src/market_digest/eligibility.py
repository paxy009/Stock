"""Geographic eligibility filter (MSCI DM reference, Poland and EM excluded)."""

from __future__ import annotations

from dataclasses import dataclass

from market_digest.config import CoverageConfig, InstrumentConfig
from market_digest.models import Eligibility


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    status: Eligibility
    reason: str


def classify(inst: InstrumentConfig, cov: CoverageConfig) -> EligibilityResult:
    if inst.eligibility_override == "excluded":
        return EligibilityResult(Eligibility.EXCLUDED, "wykluczenie ręczne w konfiguracji")
    if inst.eligibility_override == "requires_review":
        return EligibilityResult(Eligibility.REQUIRES_REVIEW, "oznaczone do weryfikacji")

    if inst.kind in ("future", "fx"):
        return EligibilityResult(Eligibility.ELIGIBLE, "cena globalna / kurs pomocniczy")

    if inst.kind == "equity":
        country = (inst.issuer_country or "").upper()
        return _by_countries(inst, cov, frozenset({country}), "kraj emitenta")

    exposure = inst.exposure_countries or frozenset()
    if not exposure:
        return EligibilityResult(Eligibility.ELIGIBLE, "instrument surowcowy / cena globalna")
    return _by_countries(inst, cov, frozenset(c.upper() for c in exposure), "ekspozycja")


def _by_countries(
    inst: InstrumentConfig, cov: CoverageConfig, countries: frozenset[str], label: str
) -> EligibilityResult:
    polish = countries & cov.explicitly_excluded_countries
    non_dm = countries - cov.developed_countries - cov.explicitly_excluded_countries
    if polish or non_dm:
        bad = ", ".join(sorted(polish | non_dm))
        if inst.role == "benchmark_only" and inst.kind != "equity":
            return EligibilityResult(
                Eligibility.BENCHMARK_ONLY,
                f"{label} obejmuje rynki spoza zakresu ({bad}) — tylko benchmark",
            )
        why = "Polska" if polish else "rynek spoza Developed Markets"
        return EligibilityResult(Eligibility.EXCLUDED, f"{label}: {bad} ({why})")
    if inst.role == "benchmark_only":
        return EligibilityResult(Eligibility.BENCHMARK_ONLY, "benchmark")
    return EligibilityResult(Eligibility.ELIGIBLE, f"{label}: {', '.join(sorted(countries))}")


def is_reportable(result: EligibilityResult) -> bool:
    """Instruments allowed in the investment part of the report (tables of movers)."""
    return result.status == Eligibility.ELIGIBLE
