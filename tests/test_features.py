from __future__ import annotations

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.storage.sqlite_store import SQLiteMarketStore
from ashare_agent.strategy.features import build_stock_features


def test_build_stock_features_creates_rush_accumulation_events() -> None:
    stocks = MockMarketDataProvider().get_stock_snapshots()
    moneyflow_rows = [
        {
            "as_of": stocks[0].timestamp.isoformat(),
            "symbol": stocks[0].symbol,
            "name": stocks[0].name,
            "pct_change": 6.2,
            "main_net_inflow": 900_000_000,
        },
        {
            "as_of": stocks[1].timestamp.isoformat(),
            "symbol": stocks[1].symbol,
            "name": stocks[1].name,
            "pct_change": 1.0,
            "main_net_inflow": 10_000_000,
        },
    ]

    features, events = build_stock_features(stocks, moneyflow_rows)

    assert features[0].rush_accumulation_score >= features[-1].rush_accumulation_score
    assert any(item.event_type == "rush_accumulation" for item in events)
    assert events[0].symbols == [stocks[0].symbol]


def test_sqlite_store_roundtrips_events_and_features(tmp_path) -> None:
    db_path = tmp_path / "market.sqlite3"
    store = SQLiteMarketStore(db_path)
    mock = MockMarketDataProvider()
    stocks = mock.get_stock_snapshots()
    limit_events = mock.get_limit_up_events()
    moneyflow_rows = [
        {
            "as_of": stocks[0].timestamp.isoformat(),
            "symbol": stocks[0].symbol,
            "name": stocks[0].name,
            "pct_change": stocks[0].pct_change,
            "main_net_inflow": stocks[0].main_net_inflow,
        }
    ]
    features, rush_events = build_stock_features(stocks, moneyflow_rows)

    assert store.save_stock_snapshots(stocks, source="test") == len(stocks)
    assert store.save_limit_up_events(limit_events, source="test") == len(limit_events)
    assert store.save_stock_features(features) == len(features)
    assert store.save_news_events(rush_events) == len(rush_events)
    assert store.delete_news_events(stocks[0].timestamp.date().isoformat(), "dragon_tiger") == 0

    assert store.load_latest_limit_up_events()[0].symbol == limit_events[0].symbol
    assert store.load_latest_limit_up_event_dicts()[0]["raw_source"] == "test"
    assert store.load_latest_stock_feature_dicts()[0]["rush_accumulation_score"] >= 0
    assert store.quality()["has_limit_up_events"] is True
    assert store.quality()["has_derived_features"] is True
