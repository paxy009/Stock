"""Section 9: user-curated claims checked against data the pipeline already has.

Free text is never parsed. Each claim carries explicit, measurable parts written by the user;
causal statements ("fell because ...") are kept as ``causal`` parts and never auto-supported.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Op = Literal["<", "<=", ">", ">=", "between"]
PRICE_METRICS = ("ret_1d", "ret_5d", "ret_21d", "ret_ytd", "drawdown_52w", "last_close",
                 "vs_sma50")
FUND_METRICS = ("revenue_yoy", "net_margin", "pe_ttm", "eps_ttm", "revenue", "fcf")
STATUSES = ("supported", "contradicted", "partially_supported", "insufficient_evidence",
            "prediction_pending")


class ClaimPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    kind: Literal["price", "macro", "fundamental", "causal"] = "price"
    symbol: str | None = None  # price/fundamental
    series: str | None = None  # macro (FRED id)
    metric: str | None = None
    op: Op | None = None
    value: float | None = None
    value2: float | None = None  # upper bound for 'between'

    @model_validator(mode="after")
    def _check(self) -> ClaimPart:
        if self.kind == "causal":
            return self
        if self.op is None or self.value is None:
            raise ValueError(f"'{self.text}': wymagane op i value")
        if self.op == "between" and self.value2 is None:
            raise ValueError(f"'{self.text}': 'between' wymaga value2")
        if self.kind == "price" and (not self.symbol or self.metric not in PRICE_METRICS):
            raise ValueError(f"'{self.text}': price wymaga symbol i metric z {PRICE_METRICS}")
        if self.kind == "fundamental" and (not self.symbol or self.metric not in FUND_METRICS):
            raise ValueError(f"'{self.text}': fundamental wymaga symbol i metric z {FUND_METRICS}")
        if self.kind == "macro" and not self.series:
            raise ValueError(f"'{self.text}': macro wymaga series (np. DGS10)")
        return self


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    source_url: str | None = None
    source_name: str = "nieznane źródło"
    claimed_at: date
    check_after: date | None = None  # predictions: not evaluated before this date
    active: bool = True
    parts: tuple[ClaimPart, ...] = Field(min_length=1)

    @property
    def claim_id(self) -> str:
        return hashlib.sha256(f"{self.text}|{self.claimed_at}".encode()).hexdigest()[:12]


class ClaimsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: tuple[Claim, ...] = ()


def load_claims(path: Path) -> list[Claim]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(ClaimsFile.model_validate(data).claims)


@dataclass(frozen=True, slots=True)
class PartResult:
    text: str
    status: Literal["true", "false", "no_data", "not_checkable"]
    observed: str
    as_of: date | None


@dataclass(frozen=True, slots=True)
class ClaimResult:
    claim: Claim
    status: str
    parts: tuple[PartResult, ...]
    reason: str


Lookup = Callable[[ClaimPart], tuple[float | None, date | None]]


def _compare(v: float, part: ClaimPart) -> bool:
    assert part.value is not None
    if part.op == "<":
        return v < part.value
    if part.op == "<=":
        return v <= part.value
    if part.op == ">":
        return v > part.value
    if part.op == ">=":
        return v >= part.value
    assert part.value2 is not None
    lo, hi = sorted((part.value, part.value2))
    return lo <= v <= hi


def _fmt(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def evaluate_claim(claim: Claim, lookup: Lookup, today: date) -> ClaimResult:
    if claim.check_after and today < claim.check_after:
        parts = tuple(PartResult(p.text, "no_data", "ocena po " + claim.check_after.isoformat(),
                                 None) for p in claim.parts)
        return ClaimResult(claim, "prediction_pending", parts,
                           f"prognoza — weryfikacja od {claim.check_after.isoformat()}")
    results: list[PartResult] = []
    for p in claim.parts:
        if p.kind == "causal":
            results.append(PartResult(p.text, "not_checkable",
                                      "związek przyczynowy — nie da się potwierdzić danymi cenowymi",
                                      None))
            continue
        v, as_of = lookup(p)
        if v is None:
            results.append(PartResult(p.text, "no_data", "brak danych", as_of))
        else:
            results.append(PartResult(p.text, "true" if _compare(v, p) else "false", _fmt(v),
                                      as_of))
    checked = [r for r in results if r.status in ("true", "false")]
    n_true = sum(1 for r in checked if r.status == "true")
    unverifiable = len(results) - len(checked)
    if not checked:
        status, reason = "insufficient_evidence", "żadnej części nie da się sprawdzić na danych"
    elif n_true == 0:
        status, reason = "contradicted", "mierzalne części sprzeczne z danymi"
    elif n_true == len(checked) and unverifiable == 0:
        status, reason = "supported", "wszystkie mierzalne części zgodne z danymi"
    elif n_true == len(checked):
        # Measurable facts hold, but e.g. the causal claim cannot be confirmed.
        status = "partially_supported"
        reason = (f"części mierzalne zgodne ({n_true}/{len(checked)}), "
                  f"{unverifiable} niesprawdzalne (np. przyczyna)")
    else:
        status = "partially_supported"
        reason = f"{n_true}/{len(checked)} mierzalnych części zgodnych"
        if unverifiable:
            reason += f"; {unverifiable} niesprawdzalne"
    return ClaimResult(claim, status, tuple(results), reason)
