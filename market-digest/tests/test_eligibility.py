from pathlib import Path
from typing import Any

import pytest

from market_digest.config import InstrumentConfig
from market_digest.eligibility import classify
from market_digest.models import Eligibility
from tests.conftest import make_config


def _inst(**kw: Any) -> InstrumentConfig:
    base: dict[str, Any] = {"symbol": "X", "name": "X", "region": "us", "currency": "USD",
                            "exchange": "XNYS"}
    return InstrumentConfig.model_validate({**base, **kw})


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({"kind": "equity", "issuer_country": "PL"}, Eligibility.EXCLUDED),  # Polska, nawet w USA
        ({"kind": "equity", "issuer_country": "TW"}, Eligibility.EXCLUDED),  # ADR emitenta EM
        ({"kind": "equity", "issuer_country": "CN"}, Eligibility.EXCLUDED),
        ({"kind": "equity", "issuer_country": "KR"}, Eligibility.EXCLUDED),
        ({"kind": "equity", "issuer_country": "NL"}, Eligibility.ELIGIBLE),  # ASML w USA
        ({"kind": "etf", "exposure_countries": ["DE", "FR", "GB"]}, Eligibility.ELIGIBLE),
        ({"kind": "etf", "exposure_countries": ["DE", "CN"]}, Eligibility.EXCLUDED),  # DM+EM
        ({"kind": "etf", "exposure_countries": ["US", "TW"], "role": "benchmark_only"},
         Eligibility.BENCHMARK_ONLY),  # SMH
        ({"kind": "equity", "issuer_country": "TW", "role": "benchmark_only"},
         Eligibility.EXCLUDED),  # spółka EM nie staje się benchmarkiem
        ({"kind": "equity", "issuer_country": "HK", "eligibility_override": "requires_review"},
         Eligibility.REQUIRES_REVIEW),
        ({"kind": "etf", "exposure_countries": []}, Eligibility.ELIGIBLE),  # surowiec
    ],
)
def test_classification(tmp_path: Path, kw: dict[str, Any], expected: Eligibility) -> None:
    cov = make_config(tmp_path).coverage
    assert classify(_inst(**kw), cov).status == expected


def test_poland_excluded_even_if_listed_as_developed(tmp_path: Path) -> None:
    cfg = make_config(tmp_path, coverage={"developed_countries": ["US", "PL"]})
    res = classify(_inst(kind="equity", issuer_country="PL"), cfg.coverage)
    assert res.status == Eligibility.EXCLUDED
    assert "Polska" in res.reason
