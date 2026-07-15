from __future__ import annotations

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.reports import render_markdown_report
from ashare_agent.strategy.scoring import get_market_overview


def main() -> None:
    print(render_markdown_report(get_market_overview(MockMarketDataProvider())))


if __name__ == "__main__":
    main()
