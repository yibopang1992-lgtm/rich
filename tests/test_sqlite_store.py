from __future__ import annotations

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.data_sources.sqlite_provider import SQLiteMarketDataProvider
from ashare_agent.storage.sqlite_store import SQLiteMarketStore
from ashare_agent.strategy.scoring import find_catchup_candidates, score_mainlines


def test_sqlite_store_roundtrip_supports_strategy(tmp_path) -> None:
    db_path = tmp_path / "market.sqlite3"
    store = SQLiteMarketStore(db_path)
    mock = MockMarketDataProvider()
    as_of = mock.as_of

    stock_rows = store.save_stock_snapshots(mock.get_stock_snapshots(), source="test")
    sector_rows = store.save_sector_snapshots(mock.get_sector_snapshots(), source="test")
    membership_rows = store.save_sector_memberships(
        as_of,
        [
            {"sector_name": "PCB", "sector_type": "concept", "symbol": "002916.SZ", "name": "深南电路"},
            {"sector_name": "PCB", "sector_type": "concept", "symbol": "603228.SH", "name": "景旺电子"},
        ],
    )

    assert stock_rows > 0
    assert sector_rows > 0
    assert membership_rows == 2

    provider = SQLiteMarketDataProvider(store)
    mainlines = score_mainlines(provider)
    candidates = find_catchup_candidates(provider, sector_names=["PCB"])

    assert mainlines[0].sector_name == "PCB"
    assert candidates
    assert candidates[0].sector_name == "PCB"


def test_sqlite_store_realtime_quotes(tmp_path) -> None:
    db_path = tmp_path / "market.sqlite3"
    store = SQLiteMarketStore(db_path)
    snapshots = MockMarketDataProvider().get_stock_snapshots()[:2]

    rows = store.save_realtime_quotes(snapshots, source="sina")
    latest = store.load_latest_realtime_quote_dicts(limit=10)

    assert rows == 2
    assert len(latest) == 2
    assert latest[0]["raw_source"] == "sina"


def test_sqlite_store_loads_latest_row_per_symbol(tmp_path) -> None:
    db_path = tmp_path / "market.sqlite3"
    store = SQLiteMarketStore(db_path)
    snapshots = MockMarketDataProvider().get_stock_snapshots()

    store.save_stock_snapshots(snapshots, source="daily")
    store.save_stock_snapshots([snapshots[0].model_copy(update={"amount": 123.0})], source="realtime")

    latest = store.load_latest_stock_snapshots()

    assert len(latest) == len(snapshots)
    assert latest[0].symbol != snapshots[0].symbol
    assert any(item.symbol == snapshots[0].symbol and item.amount == 123.0 for item in latest)
    assert len(store.load_latest_symbols()) == len(snapshots)
