from __future__ import annotations

from fastapi.testclient import TestClient

from ashare_agent.apps.api import main as api_main
from ashare_agent.data_sources.mock import MockMarketDataProvider


def test_new_strategy_endpoints_return_structured_payloads(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "get_provider", lambda: (MockMarketDataProvider(), "mock"))
    client = TestClient(api_main.create_app())

    linkage = client.get("/strategy/limitup-linkage").json()
    high_low = client.get("/strategy/high-low-switch").json()

    assert isinstance(linkage, list)
    assert isinstance(high_low, list)
    if linkage:
        assert {"sector_name", "limit_up_count", "leader_symbol", "trigger_conditions"} <= set(linkage[0])
    if high_low:
        assert {"symbol", "sector_name", "preconditions", "invalid_conditions"} <= set(high_low[0])
