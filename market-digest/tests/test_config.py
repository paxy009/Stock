from pathlib import Path

import pytest
from pydantic import ValidationError

from market_digest.config import load_config
from tests.conftest import make_config

ROOT = Path(__file__).resolve().parents[1]


def test_repository_config_is_valid() -> None:
    cfg = load_config(ROOT / "config.yaml")
    assert {"us", "developed_europe", "developed_asia"} <= {i.region for i in cfg.instruments}
    assert "PL" in cfg.coverage.explicitly_excluded_countries
    assert "PL" not in cfg.coverage.developed_countries


def test_equity_requires_issuer_country(tmp_path: Path) -> None:
    bad = [{"symbol": "X", "name": "X", "kind": "equity", "region": "us", "currency": "USD",
            "exchange": "XNYS"}]
    with pytest.raises(ValidationError, match="issuer_country"):
        make_config(tmp_path, bad)


def test_unknown_benchmark_rejected(tmp_path: Path) -> None:
    bad = [{"symbol": "X", "name": "X", "kind": "equity", "region": "us", "currency": "USD",
            "exchange": "XNYS", "issuer_country": "US", "benchmark": "NOPE"}]
    with pytest.raises(ValidationError, match="benchmark"):
        make_config(tmp_path, bad)


def test_unknown_keys_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        make_config(tmp_path, smtp_password="secret")
