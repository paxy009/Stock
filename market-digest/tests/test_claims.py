from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from market_digest.claims import Claim, ClaimPart, evaluate_claim, load_claims

TODAY = date(2026, 11, 23)
ROOT = Path(__file__).resolve().parents[1]


def _claim(*parts: ClaimPart, check_after: date | None = None) -> Claim:
    return Claim(text="t", claimed_at=TODAY, check_after=check_after, parts=parts)


def P(**kw: object) -> ClaimPart:
    return ClaimPart.model_validate({"text": "p", **kw})


def lookup_from(values: dict[str, float | None]):  # type: ignore[no-untyped-def]
    def f(p: ClaimPart) -> tuple[float | None, date | None]:
        key = f"{p.symbol or p.series}.{p.metric or ''}"
        return values.get(key), TODAY
    return f


def test_supported_and_contradicted() -> None:
    lk = lookup_from({"NVDA.ret_5d": -12.0})
    ok = evaluate_claim(_claim(P(symbol="NVDA", metric="ret_5d", op="<", value=-10)), lk, TODAY)
    bad = evaluate_claim(_claim(P(symbol="NVDA", metric="ret_5d", op=">", value=0)), lk, TODAY)
    assert ok.status == "supported" and bad.status == "contradicted"


def test_causal_part_prevents_full_support() -> None:
    lk = lookup_from({"NVDA.ret_5d": -12.0})
    r = evaluate_claim(_claim(P(symbol="NVDA", metric="ret_5d", op="<", value=-10),
                              P(kind="causal")), lk, TODAY)
    assert r.status == "partially_supported"
    assert "niesprawdzalne" in r.reason


def test_only_causal_is_insufficient() -> None:
    r = evaluate_claim(_claim(P(kind="causal")), lookup_from({}), TODAY)
    assert r.status == "insufficient_evidence"


def test_missing_data_is_not_contradiction() -> None:
    r = evaluate_claim(_claim(P(symbol="XYZ", metric="ret_5d", op="<", value=0)),
                       lookup_from({}), TODAY)
    assert r.status == "insufficient_evidence"


def test_mixed_parts() -> None:
    lk = lookup_from({"A.ret_1d": 1.0, "B.ret_1d": -1.0})
    r = evaluate_claim(_claim(P(symbol="A", metric="ret_1d", op=">", value=0),
                              P(symbol="B", metric="ret_1d", op=">", value=0)), lk, TODAY)
    assert r.status == "partially_supported" and r.reason.startswith("1/2")


def test_prediction_pending_before_check_date() -> None:
    lk = lookup_from({"A.ret_1d": 5.0})
    part = P(symbol="A", metric="ret_1d", op=">", value=0)
    assert evaluate_claim(_claim(part, check_after=date(2026, 12, 31)), lk,
                          TODAY).status == "prediction_pending"
    assert evaluate_claim(_claim(part, check_after=date(2026, 12, 31)), lk,
                          date(2026, 12, 31)).status == "supported"


def test_between() -> None:
    part = P(kind="macro", series="DGS10", op="between", value=5.5, value2=4.5)
    assert evaluate_claim(_claim(part), lookup_from({"DGS10.": 5.0}), TODAY).status == "supported"


def test_validation_rejects_bad_parts() -> None:
    with pytest.raises(ValidationError):
        P(symbol="NVDA", metric="ret_5d")  # missing op/value
    with pytest.raises(ValidationError):
        P(symbol="NVDA", metric="made_up", op="<", value=1)
    with pytest.raises(ValidationError):
        P(kind="macro", op="<", value=1)


def test_example_claims_file_is_valid() -> None:
    claims = load_claims(ROOT / "claims.yaml")
    assert len(claims) >= 1
    assert load_claims(ROOT / "does-not-exist.yaml") == []


def test_section_9_in_report_and_status_history(tmp_path: Path) -> None:
    from datetime import timedelta

    from market_digest import pipeline
    from market_digest.config import ClaimsConfig
    from market_digest.storage import Storage
    from tests.conftest import FakeCalendar, make_config
    from tests.test_pipeline import NOW, _news, _prices

    cf = tmp_path / "claims.yaml"
    cf.write_text(
        "claims:\n"
        "  - text: 'SPY rosło w tym miesiącu'\n"
        "    source_name: blog\n"
        "    source_url: 'https://blog.example.net/post'\n"
        "    claimed_at: 2025-11-20\n"
        "    parts:\n"
        "      - {text: 'SPY 21 sesji > 0', kind: price, symbol: SPY, metric: ret_21d, op: '>', value: 0}\n",
        encoding="utf-8")
    cfg = make_config(tmp_path).model_copy(update={"claims": ClaimsConfig(path=cf)})
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    md = pipeline.generate(cfg, st, FakeCalendar(), NOW).report_path.read_text(  # type: ignore[union-attr]
        encoding="utf-8")
    s9 = md.split("## 9.")[1].split("## 10.")[0]
    assert "**supported** (potwierdzona)" in s9
    assert "[blog](https://blog.example.net/post)" in s9  # source URL allowed by QA
    assert "✅ SPY 21 sesji > 0" in s9

    # Next day the claim turns false -> status change is shown
    nxt = NOW + timedelta(days=1)
    cf.write_text(cf.read_text(encoding="utf-8").replace("op: '>'", "op: '<'"), encoding="utf-8")
    pipeline.fetch(cfg, st, _prices(), _news(), nxt)
    md2 = pipeline.generate(cfg, st, FakeCalendar(), nxt).report_path.read_text(  # type: ignore[union-attr]
        encoding="utf-8")
    assert "zmiana z supported (2025-11-24)" in md2.split("## 9.")[1]


def test_broken_claims_file_does_not_stop_report(tmp_path: Path) -> None:
    from market_digest import pipeline
    from market_digest.config import ClaimsConfig
    from market_digest.storage import Storage
    from tests.conftest import FakeCalendar, make_config
    from tests.test_pipeline import NOW, _news, _prices

    cf = tmp_path / "claims.yaml"
    cf.write_text("claims:\n  - text: x\n", encoding="utf-8")  # missing fields
    cfg = make_config(tmp_path).model_copy(update={"claims": ClaimsConfig(path=cf)})
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    md = pipeline.generate(cfg, st, FakeCalendar(), NOW).report_path.read_text(  # type: ignore[union-attr]
        encoding="utf-8")
    assert "claims.yaml (ValidationError)" in md
