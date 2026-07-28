from __future__ import annotations

from datetime import date, datetime

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.models import NewsEvent
from ashare_agent.models import SectorSnapshot, SectorType
from ashare_agent.scripts import sync_market_data as sync_module
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


def test_instock_em_refreshes_quotes_events_and_features_before_memberships(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "market.sqlite3"
    mock = MockMarketDataProvider()
    stock = mock.get_stock_snapshots()[0]
    as_of = datetime(2026, 7, 28, 10, 30, tzinfo=stock.timestamp.tzinfo)
    stock = stock.model_copy(update={"timestamp": as_of, "amount": 2_500_000_000, "turnover_rate": 12.3})
    sector = SectorSnapshot(
        sector_id="instock_em_concept_PCB",
        sector_name="PCB",
        sector_type=SectorType.CONCEPT,
        timestamp=as_of,
        pct_change=3.2,
        main_net_inflow=1_000_000_000,
        amount=8_000_000_000,
        amount_growth=0,
        up_count=10,
        down_count=2,
        limit_up_count=2,
        breadth=10 / 12,
    )

    monkeypatch.setattr(sync_module, "fetch_instock_all_sector_fund_flow", lambda trade_date: [sector])
    monkeypatch.setattr(sync_module, "fetch_instock_stock_moneyflow", lambda trade_date: [stock])
    monkeypatch.setattr(sync_module, "fetch_limit_up_events", lambda trade_date: (mock.get_limit_up_events(), []))
    monkeypatch.setattr(
        sync_module,
        "fetch_dragon_tiger_events",
        lambda trade_date: [
            NewsEvent(
                event_id="dragon_tiger:test",
                timestamp=as_of,
                source="test",
                title="test",
                symbols=[stock.symbol],
                event_type="dragon_tiger",
                sentiment=0,
                importance=50,
            )
        ],
    )
    monkeypatch.setattr(sync_module, "fetch_sector_memberships", lambda sectors, per_type_limit=8: (_ for _ in ()).throw(AssertionError))

    result = sync_market_data(db_path=str(db_path), provider="instock-em", trade_date=date(2026, 7, 28))
    store = SQLiteMarketStore(db_path)
    quality = store.quality()
    features = store.load_latest_stock_feature_dicts(limit=1)

    assert result["stock_rows"] == 1
    assert result["realtime_rows"] == 1
    assert result["moneyflow_rows"] == 1
    assert result["sector_rows"] == 1
    assert result["membership_rows"] == 0
    assert result["limit_up_rows"] == len(mock.get_limit_up_events())
    assert result["news_event_rows"] >= 1
    assert result["feature_rows"] == 1
    assert quality["latest_stock_as_of"] == as_of.isoformat()
    assert quality["latest_realtime_as_of"] == as_of.isoformat()
    assert features[0]["amount"] == 2_500_000_000
    assert features[0]["turnover_rate"] == 12.3


def test_full_refreshes_sector_memberships_after_features(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "market.sqlite3"
    mock = MockMarketDataProvider()
    stock = mock.get_stock_snapshots()[0]
    as_of = datetime(2026, 7, 28, 10, 30, tzinfo=stock.timestamp.tzinfo)
    stock = stock.model_copy(update={"timestamp": as_of, "amount": 2_500_000_000, "turnover_rate": 12.3})
    sector = SectorSnapshot(
        sector_id="instock_em_concept_PCB",
        sector_name="PCB",
        sector_type=SectorType.CONCEPT,
        timestamp=as_of,
        pct_change=3.2,
        main_net_inflow=1_000_000_000,
        amount=8_000_000_000,
        amount_growth=0,
        up_count=10,
        down_count=2,
        limit_up_count=2,
        breadth=10 / 12,
    )

    monkeypatch.setattr(sync_module, "fetch_instock_all_sector_fund_flow", lambda trade_date: [sector])
    monkeypatch.setattr(sync_module, "fetch_instock_stock_moneyflow", lambda trade_date: [stock])
    monkeypatch.setattr(sync_module, "fetch_limit_up_events", lambda trade_date: ([], []))
    monkeypatch.setattr(sync_module, "fetch_dragon_tiger_events", lambda trade_date: [])
    monkeypatch.setattr(
        sync_module,
        "fetch_sector_memberships",
        lambda sectors, per_type_limit=8: [
            {
                "sector_name": "PCB",
                "sector_type": "concept",
                "symbol": stock.symbol,
                "name": stock.name,
            }
        ],
    )

    result = sync_market_data(db_path=str(db_path), provider="full", trade_date=date(2026, 7, 28))
    store = SQLiteMarketStore(db_path)

    assert result["feature_rows"] == 1
    assert result["membership_rows"] == 1
    assert store.load_latest_stock_feature_dicts(limit=1)[0]["amount"] == 2_500_000_000
    assert store.quality()["latest_membership_as_of"] is not None
