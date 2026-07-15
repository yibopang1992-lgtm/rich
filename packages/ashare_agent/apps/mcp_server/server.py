from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ashare_agent.data_sources.provider_factory import get_provider
from ashare_agent.reports import render_markdown_report
from ashare_agent.strategy.scoring import (
    find_catchup_candidates,
    find_leaders,
    get_market_overview,
    get_rotation_status,
    run_mock_backtest,
    score_mainlines,
)


mcp = FastMCP(
    "ashare_rotation",
    instructions=(
        "Research-only A-share capital rotation tools. Do not present outputs as "
        "investment advice. Always preserve timestamps, reasons, risks, triggers, "
        "and invalidation conditions. Check provider/data mode before relying on live conclusions."
    ),
)


@mcp.tool()
def get_market_overview_tool() -> dict:
    """Return market overview with mainlines, leaders, catch-up candidates, and rotation status."""
    provider, provider_mode = get_provider()
    result = get_market_overview(provider).model_dump(mode="json")
    result["provider_mode"] = provider_mode
    return result


@mcp.tool()
def get_mainline_scores_tool() -> list[dict]:
    """Return ranked sector mainline scores."""
    provider, _ = get_provider()
    return [item.model_dump(mode="json") for item in score_mainlines(provider)]


@mcp.tool()
def get_leader_candidates_tool(max_items: int = 5) -> list[dict]:
    """Return leader observation symbols. Leaders are not automatic buy candidates."""
    provider, _ = get_provider()
    return [item.model_dump(mode="json") for item in find_leaders(provider, max_items=max_items)]


@mcp.tool()
def get_catchup_candidates_tool(
    sector_names: list[str] | None = None,
    max_candidates: int = 5,
    exclude_limit_up: bool = True,
    max_recent_5d_gain: float = 20,
) -> list[dict]:
    """Return catch-up candidates with reasons, risks, triggers, and invalidation conditions."""
    provider, _ = get_provider()
    return [
        item.model_dump(mode="json")
        for item in find_catchup_candidates(
            provider,
            sector_names=sector_names,
            max_candidates=max_candidates,
            exclude_limit_up=exclude_limit_up,
            max_recent_5d_gain=max_recent_5d_gain,
        )
    ]


@mcp.tool()
def get_rotation_status_tool() -> dict:
    """Return sector rotation status and confirmation risk."""
    provider, _ = get_provider()
    return get_rotation_status(provider).model_dump(mode="json")


@mcp.tool()
def run_daily_backtest_tool() -> dict:
    """Run the mock daily catch-up strategy backtest scaffold."""
    provider, provider_mode = get_provider()
    result = run_mock_backtest(provider).model_dump(mode="json")
    result["provider_mode"] = provider_mode
    return result


@mcp.tool()
def generate_trading_report_tool() -> str:
    """Generate the daily markdown research report."""
    provider, _ = get_provider()
    return render_markdown_report(get_market_overview(provider))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
