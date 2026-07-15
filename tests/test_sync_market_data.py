from __future__ import annotations

from datetime import date

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.scripts.sync_market_data import sync_market_data
from ashare_agent.storage.sqlite_store import SQLiteMarketStore


def test_derived_features_respect_trade_date(tmp_path) -> None:
    db_path = tmp_path / "market.sqlite3"
    store = SQLiteMarketStore(db_path)
    store.init_db()
    mock = MockMarketDataProvider()
    old_day = date(2026, 7, 14)
    latest_day = date(2026, 7, 15)
    old_snapshots = [
        item.model_copy(update={"timestamp": item.timestamp.replace(year=old_day.year, month=old_day.month, day=old_day.day)})
        for item in mock.get_stock_snapshots()[:2]
    ]
    latest_snapshots = [
        item.model_copy(
            update={"timestamp": item.timestamp.replace(year=latest_day.year, month=latest_day.month, day=latest_day.day)}
        )
        for item in mock.get_stock_snapshots()
    ]
    store.save_stock_snapshots(old_snapshots, source="old")
    store.save_stock_snapshots(latest_snapshots, source="latest")

    result = sync_market_data(
        db_path=str(db_path),
        provider="derived-features",
        trade_date=old_day,
    )

    assert result["feature_rows"] == len(old_snapshots)
