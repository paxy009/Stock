from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from market_digest import pipeline
from market_digest.config import Config
from market_digest.models import NewsItem, PriceBar
from market_digest.providers.news import StaticNewsProvider
from market_digest.providers.prices import StaticPriceProvider
from market_digest.storage import Storage
from tests.conftest import FakeCalendar, bars_from, news

MON = date(2025, 11, 24)
MON_AT = datetime(2025, 11, 24, 22, 30, tzinfo=UTC)
TUE_AT = MON_AT + timedelta(days=1)
SAT_AT = datetime(2025, 11, 29, 22, 30, tzinfo=UTC)


def _prices(end: date, spy_next: float | None = None, split_spy: bool = False
            ) -> StaticPriceProvider:
    """SPY closes at 530 on MON; optionally ``spy_next`` on the following session."""
    data: dict[str, list[PriceBar]] = {}
    for sym, base in (("VGK", 70.0), ("EWJ", 70.0), ("NVDA", 180.0)):
        data[sym] = bars_from([base + i for i in range(30)], end)
    spy = [500.0] * 28 + [530.0] + ([spy_next] if spy_next is not None else [])
    data["SPY"] = bars_from(spy, end)
    if split_spy:  # provider re-based all history 2:1 after a split
        data["SPY"] = [PriceBar(b.session_date, (b.close or 0) / 2, (b.adj_close or 0) / 2)
                       for b in data["SPY"]]
    data["USDPLN=X"] = bars_from([4.0] * 30, end)
    return StaticPriceProvider(data)


def _report(cfg: Config, st: Storage, at: datetime, prices: StaticPriceProvider,
            items: list[NewsItem] | None = None) -> str:
    pipeline.fetch(cfg, st, prices, StaticNewsProvider(items or []), at)
    res = pipeline.generate(cfg, st, FakeCalendar(), at)
    assert res.report_path is not None
    md: str = res.report_path.read_text(encoding="utf-8")
    return md.split("## 2.")[1].split("## 3.")[0]


def test_first_report_has_no_comparison(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    s2 = _report(cfg, st, MON_AT, _prices(MON))
    assert "Brak wcześniejszego raportu" in s2


def test_price_move_between_reports(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    _report(cfg, st, MON_AT, _prices(MON))
    s2 = _report(cfg, st, TUE_AT, _prices(MON + timedelta(days=1), spy_next=540.0))
    assert "Porównanie z raportem z **2025-11-24**" in s2
    spy = next(ln for ln in s2.splitlines() if ln.startswith("| SPY"))
    assert "530,00 (2025-11-24)" in spy and "540,00 (2025-11-25)" in spy
    assert "+1,89%" in spy  # 540/530-1


def test_weekend_report_says_no_new_session_not_zero(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    fri = date(2025, 11, 28)
    _report(cfg, st, datetime(2025, 11, 28, 22, 30, tzinfo=UTC), _prices(fri))
    s2 = _report(cfg, st, SAT_AT, _prices(fri))
    assert "Bez nowej sesji od poprzedniego raportu:** SPY, VGK, EWJ" in s2
    assert "+0,00%" not in s2


def test_split_after_previous_report_is_not_a_fake_crash(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    _report(cfg, st, MON_AT, _prices(MON))
    s2 = _report(cfg, st, TUE_AT, _prices(MON + timedelta(days=1), spy_next=540.0,
                                         split_spy=True))
    spy = next(ln for ln in s2.splitlines() if ln.startswith("| SPY"))
    assert "265,00 (2025-11-24)" in spy and "+1,89%" in spy  # 270/265 after re-basing
    assert "-49" not in spy
    assert "split/korekta danych" in s2


def test_new_event_and_followup(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    a = news("Fed holds rates steady at November meeting", "https://fed.gov/a",
             MON_AT - timedelta(hours=2))
    _report(cfg, st, MON_AT, _prices(MON), [a])
    b = news("ECB publishes financial stability review", "https://ecb.eu/b",
             TUE_AT - timedelta(hours=1), feed="ecb")
    a2 = news("Fed holds rates steady at its November meeting", "https://media.net/x",
              TUE_AT - timedelta(hours=3), feed="m", tier="media")
    s2 = _report(cfg, st, TUE_AT, _prices(MON + timedelta(days=1)), [a, a2, b])
    assert "Nowe potwierdzone wydarzenia:** [ECB publishes financial stability review]" in s2
    assert "Nowe informacje w istniejących sprawach:** [Fed holds rates steady" in s2
    assert "(+1 nowe źródło/a)" in s2


def test_compares_with_latest_earlier_date_not_same_day(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    _report(cfg, st, MON_AT, _prices(MON))
    pipeline.generate(cfg, st, FakeCalendar(), MON_AT, force=True)  # 2nd version same day
    prev = st.previous_snapshot(MON + timedelta(days=1))
    assert prev is not None and prev[0] == MON
    assert st.previous_snapshot(MON) is None
