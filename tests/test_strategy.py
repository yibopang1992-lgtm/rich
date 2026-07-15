from __future__ import annotations

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.models import LimitUpEvent
from ashare_agent.models import CandidateTier, SectorStage
from ashare_agent.reports import render_markdown_report
from ashare_agent.strategy.scoring import (
    analyze_limitup_linkage,
    find_catchup_candidates,
    find_high_low_switch_signals,
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


def test_limitup_linkage_requires_three_same_sector_limitups_and_marks_one_leader() -> None:
    class LinkageProvider(MockMarketDataProvider):
        def get_limit_up_events(self):
            base = super().get_limit_up_events()
            return [
                *base,
                base[0].model_copy(
                    update={
                        "symbol": "002916.SZ",
                        "name": "深南电路",
                        "consecutive_boards": 1,
                        "first_limit_time": "10:02:00",
                    }
                ),
            ]

    signals = analyze_limitup_linkage(LinkageProvider(), min_market_limitups=0)
    pcb = next(item for item in signals if item.sector_name == "PCB")

    assert pcb.is_linked
    assert pcb.limit_up_count == 3
    assert pcb.leader_symbol == "300476.SZ"
    assert "002916.SZ" in pcb.follower_symbols
    assert any("仅标一只龙头" in reason for reason in pcb.reasons)


def test_high_low_switch_filters_middle_and_accelerated_names() -> None:
    class HighLowProvider(MockMarketDataProvider):
        def get_stock_snapshots(self):
            rows = super().get_stock_snapshots()
            low = rows[2].model_copy(
                update={
                    "symbol": "600999.SH",
                    "name": "低位补涨",
                    "price": 9.8,
                    "pct_change": 2.6,
                    "recent_5d_gain": 1.2,
                    "market_cap": 3_800_000_000,
                    "amount": 620_000_000,
                    "main_net_inflow": 52_000_000,
                    "sector_names": ["PCB"],
                }
            )
            middle = rows[2].model_copy(
                update={
                    "symbol": "601999.SH",
                    "name": "中位加速",
                    "price": 18.0,
                    "pct_change": 5.8,
                    "recent_5d_gain": 18.0,
                    "market_cap": 4_000_000_000,
                    "sector_names": ["PCB"],
                }
            )
            return [*rows, low, middle]

    signals = find_high_low_switch_signals(HighLowProvider(), sector_names=["PCB"], max_candidates=10)

    assert any(item.symbol == "600999.SH" for item in signals)
    assert all(item.symbol != "601999.SH" for item in signals)
    assert all(item.symbol != "300476.SZ" for item in signals)
    assert all(item.trigger_conditions and item.invalid_conditions for item in signals)


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
