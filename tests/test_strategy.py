from __future__ import annotations

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.models import LimitUpEvent
from ashare_agent.models import CandidateTier, SectorStage
from ashare_agent.reports import render_markdown_report
from ashare_agent.strategy.scoring import (
    find_catchup_candidates,
    get_market_overview,
    run_mock_backtest,
    score_mainlines,
)


def test_mainline_scoring_ranks_pcb_first() -> None:
    scores = score_mainlines(MockMarketDataProvider())

    assert scores[0].sector_name == "PCB"
    assert scores[0].score >= 80
    assert scores[0].stage in {SectorStage.MARKUP, SectorStage.CLIMAX}
    assert scores[-1].sector_name == "消费电子"


def test_catchup_candidates_include_risk_controls() -> None:
    candidates = find_catchup_candidates(MockMarketDataProvider(), sector_names=["PCB"])

    assert candidates
    assert candidates[0].symbol == "002916.SZ"
    assert candidates[0].tier in {CandidateTier.CORE, CandidateTier.WATCH, CandidateTier.BACKUP}
    assert candidates[0].trigger_conditions
    assert candidates[0].invalid_conditions
    assert all(not item.symbol.startswith("300476") for item in candidates)


def test_catchup_candidates_fallback_to_amount_heat_without_money_flow() -> None:
    class AmountOnlyProvider(MockMarketDataProvider):
        def get_sector_snapshots(self):
            return [
                item.model_copy(update={"main_net_inflow": 0, "limit_up_count": 0})
                for item in super().get_sector_snapshots()
            ]

        def get_stock_snapshots(self):
            return [
                item.model_copy(update={"main_net_inflow": 0, "large_order_net_inflow": 0})
                for item in super().get_stock_snapshots()
            ]

        def get_limit_up_events(self) -> list[LimitUpEvent]:
            return []

    candidates = find_catchup_candidates(AmountOnlyProvider(), sector_names=["PCB"])

    assert candidates
    assert candidates[0].score <= 78
    assert "main inflow unavailable" in candidates[0].reasons
    assert any("amount heat" in risk for risk in candidates[0].risks)


def test_market_overview_and_report_are_research_bounded() -> None:
    overview = get_market_overview(MockMarketDataProvider())
    report = render_markdown_report(overview)

    assert overview.data_mode == "mock"
    assert "not investment advice" in report
    assert "Leader Observation" in report
    assert "Catch-up Candidates" in report


def test_mock_backtest_has_no_future_data_claims() -> None:
    result = run_mock_backtest(MockMarketDataProvider())

    assert result.sample_size == len(result.trades)
    assert result.sample_size > 0
    assert 0 <= result.win_rate <= 1
