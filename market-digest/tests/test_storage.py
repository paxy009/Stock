from datetime import UTC, date, datetime

from market_digest.models import PriceBar
from market_digest.storage import Storage
from tests.conftest import news

NOW = datetime(2025, 11, 24, 22, tzinfo=UTC)


def test_migrations_are_idempotent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "db.sqlite"
    Storage(path).close()
    st = Storage(path)
    assert st.schema_version() == 1


def test_price_upsert_does_not_duplicate() -> None:
    st = Storage(":memory:")
    st.upsert_source("yfinance", "prices", "Yahoo", None)
    bars = [PriceBar(date(2025, 11, 21), 100.0, 99.0)]
    st.upsert_prices("SPY", bars, "yfinance", NOW)
    st.upsert_prices("SPY", [PriceBar(date(2025, 11, 21), 101.0, 100.0)], "yfinance", NOW)
    loaded = st.load_prices("SPY", "yfinance")
    assert len(loaded) == 1 and loaded[0].close == 101.0


def test_news_roundtrip_and_dedup() -> None:
    st = Storage(":memory:")
    item = news("Title", "https://a.net/x", NOW)
    assert st.upsert_news([item, item]) == 1
    loaded = st.load_news(datetime(2025, 11, 1, tzinfo=UTC))
    assert loaded[0].title == "Title" and loaded[0].published_at_utc == NOW


def test_null_prices_stay_null() -> None:
    st = Storage(":memory:")
    st.upsert_source("yfinance", "prices", "Yahoo", None)
    st.upsert_prices("X", [PriceBar(date(2025, 11, 21), 10.0, None)], "yfinance", NOW)
    assert st.load_prices("X", "yfinance")[0].adj_close is None
