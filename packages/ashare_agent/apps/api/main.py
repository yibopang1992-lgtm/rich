from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from datetime import date

from ashare_agent.data_sources.provider_factory import get_provider
from ashare_agent.models import (
    BacktestResult,
    CatchupCandidate,
    HighLowSwitchSignal,
    MainlineScore,
    MarketOverview,
    RotationStatus,
    SectorLimitupLinkage,
)
from ashare_agent.reports import render_markdown_report
from ashare_agent.scripts.sync_market_data import sync_market_data
from ashare_agent.settings import get_db_path
from ashare_agent.storage.sqlite_store import SQLiteMarketStore
from ashare_agent.strategy.scoring import (
    analyze_limitup_linkage,
    find_catchup_candidates,
    find_high_low_switch_signals,
    get_market_overview,
    get_rotation_status,
    run_mock_backtest,
    score_mainlines,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="A-share Rotation Agent",
        version="0.1.0",
        description="Research-only MVP for A-share capital rotation analysis.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        _, provider_mode = get_provider()
        return {"status": "ok", "provider_mode": provider_mode, "db_path": str(get_db_path())}

    @app.get("/data/status")
    def data_status() -> dict:
        return SQLiteMarketStore(get_db_path()).status()

    @app.get("/data/quality")
    def data_quality() -> dict:
        return SQLiteMarketStore(get_db_path()).quality()

    @app.post("/data/sync")
    def data_sync(
        membership_limit: int = 8,
        provider: str = "auto",
        trade_date: date | None = None,
        max_symbols: int | None = None,
        symbols: str = "",
    ) -> dict[str, object]:
        parsed_symbols = [item.strip() for item in symbols.split(",") if item.strip()] or None
        return sync_market_data(
            membership_limit=membership_limit,
            provider=provider,
            trade_date=trade_date,
            max_symbols=max_symbols,
            symbols=parsed_symbols,
        )

    @app.get("/data/stocks/latest")
    def latest_stocks(limit: int = 50) -> list[dict]:
        return SQLiteMarketStore(get_db_path()).load_latest_stock_snapshot_dicts(limit=limit)

    @app.get("/data/realtime/latest")
    def latest_realtime(limit: int = 50) -> list[dict]:
        return SQLiteMarketStore(get_db_path()).load_latest_realtime_quote_dicts(limit=limit)

    @app.get("/data/moneyflow/latest")
    def latest_moneyflow(limit: int = 50) -> list[dict]:
        return SQLiteMarketStore(get_db_path()).load_latest_moneyflow_dicts(limit=limit)

    @app.get("/data/features/latest")
    def latest_features(limit: int = 50) -> list[dict]:
        return SQLiteMarketStore(get_db_path()).load_latest_stock_feature_dicts(limit=limit)

    @app.get("/data/events/limit-up/latest")
    def latest_limit_up_events(limit: int = 100) -> list[dict]:
        return SQLiteMarketStore(get_db_path()).load_latest_limit_up_event_dicts(limit=limit)

    @app.get("/data/events/latest")
    def latest_events(limit: int = 100, event_type: str | None = None) -> list[dict]:
        return SQLiteMarketStore(get_db_path()).load_latest_news_event_dicts(event_type=event_type, limit=limit)

    @app.get("/market/overview", response_model=MarketOverview)
    def market_overview() -> MarketOverview:
        provider, provider_mode = get_provider()
        overview = get_market_overview(provider)
        overview.data_mode = "live" if provider_mode == "sqlite" else "mock"
        return overview

    @app.get("/strategy/mainlines", response_model=list[MainlineScore])
    def mainlines() -> list[MainlineScore]:
        provider, _ = get_provider()
        return score_mainlines(provider)

    @app.get("/strategy/catchup-candidates", response_model=list[CatchupCandidate])
    def catchup_candidates(max_candidates: int = 5) -> list[CatchupCandidate]:
        provider, _ = get_provider()
        return find_catchup_candidates(provider, max_candidates=max_candidates)

    @app.get("/strategy/limitup-linkage", response_model=list[SectorLimitupLinkage])
    def limitup_linkage(max_items: int = 10) -> list[SectorLimitupLinkage]:
        provider, _ = get_provider()
        return analyze_limitup_linkage(provider, max_items=max_items)

    @app.get("/strategy/high-low-switch", response_model=list[HighLowSwitchSignal])
    def high_low_switch(max_candidates: int = 8) -> list[HighLowSwitchSignal]:
        provider, _ = get_provider()
        return find_high_low_switch_signals(provider, max_candidates=max_candidates)

    @app.get("/strategy/rotation", response_model=RotationStatus)
    def rotation() -> RotationStatus:
        provider, _ = get_provider()
        return get_rotation_status(provider)

    @app.get("/backtest/daily", response_model=BacktestResult)
    def daily_backtest() -> BacktestResult:
        provider, _ = get_provider()
        return run_mock_backtest(provider)

    @app.get("/reports/daily", response_model=str)
    def daily_report() -> str:
        provider, provider_mode = get_provider()
        overview = get_market_overview(provider)
        overview.data_mode = "live" if provider_mode == "sqlite" else "mock"
        return render_markdown_report(overview)

    return app


app = create_app()


def main() -> None:
    uvicorn.run("ashare_agent.apps.api.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
