from __future__ import annotations

from ashare_agent.data_sources.base import MarketDataProvider
from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.data_sources.sqlite_provider import SQLiteMarketDataProvider
from ashare_agent.settings import get_data_mode, get_db_path
from ashare_agent.storage.sqlite_store import SQLiteMarketStore


def get_provider() -> tuple[MarketDataProvider, str]:
    mode = get_data_mode()
    if mode == "mock":
        return MockMarketDataProvider(), "mock"

    store = SQLiteMarketStore(get_db_path())
    provider = SQLiteMarketDataProvider(store)
    if mode == "sqlite":
        return provider, "sqlite"

    if provider.has_data():
        return provider, "sqlite"
    return MockMarketDataProvider(), "mock_fallback"
