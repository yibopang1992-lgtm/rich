from __future__ import annotations

from typing import Protocol

from ashare_agent.models import LimitUpEvent, SectorSnapshot, StockSnapshot


class MarketDataProvider(Protocol):
    """Read-only market data contract used by the strategy layer."""

    def get_sector_snapshots(self) -> list[SectorSnapshot]:
        ...

    def get_stock_snapshots(self) -> list[StockSnapshot]:
        ...

    def get_limit_up_events(self) -> list[LimitUpEvent]:
        ...
