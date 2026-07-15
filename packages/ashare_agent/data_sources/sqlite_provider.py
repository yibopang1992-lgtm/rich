from __future__ import annotations

from ashare_agent.models import LimitUpEvent, SectorSnapshot, StockSnapshot
from ashare_agent.storage.sqlite_store import SQLiteMarketStore


class SQLiteMarketDataProvider:
    def __init__(self, store: SQLiteMarketStore) -> None:
        self.store = store

    def get_sector_snapshots(self) -> list[SectorSnapshot]:
        return self.store.load_latest_sector_snapshots()

    def get_stock_snapshots(self) -> list[StockSnapshot]:
        return self.store.load_latest_stock_snapshots()

    def get_limit_up_events(self) -> list[LimitUpEvent]:
        return self.store.load_latest_limit_up_events()

    def has_data(self) -> bool:
        return bool(self.get_sector_snapshots() and self.get_stock_snapshots())
