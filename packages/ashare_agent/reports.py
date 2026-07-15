from __future__ import annotations

from ashare_agent.models import MarketOverview


def render_markdown_report(overview: MarketOverview) -> str:
    lines: list[str] = [
        "# A-share Capital Rotation Report",
        "",
        "This report is for research only and is not investment advice.",
        "",
        "## Market State",
        "",
        f"- Data mode: {overview.data_mode}",
        f"- Data timestamp: {overview.as_of.isoformat()}",
        f"- Market sentiment: {overview.market_sentiment}",
        f"- Rotation confirmed: {overview.rotation_status.is_confirmed}",
        "",
        "## Mainline Cycle",
        "",
        "| Sector | Score | Stage | Tier | Risk |",
        "|---|---:|---|---|---|",
    ]

    for item in overview.mainlines:
        risk = "; ".join(item.risks) if item.risks else "none flagged"
        lines.append(f"| {item.sector_name} | {item.score:.1f} | {item.stage.value} | {item.tier} | {risk} |")

    lines.extend(
        [
            "",
            "## Leader Observation",
            "",
            "| Symbol | Name | Sector | Role | Score | Use |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for item in overview.leaders:
        lines.append(
            f"| {item.symbol} | {item.name} | {item.sector_name} | {item.role.value} | "
            f"{item.score:.1f} | observe sector strength only |"
        )

    lines.extend(
        [
            "",
            "## Catch-up Candidates",
            "",
            "| Rank | Symbol | Name | Score | Logic | Trigger | Invalidation |",
            "|---:|---|---|---:|---|---|---|",
        ]
    )
    for rank, item in enumerate(overview.catchup_candidates, start=1):
        logic = "; ".join(item.reasons[:2])
        trigger = "; ".join(item.trigger_conditions[:2])
        invalid = "; ".join(item.invalid_conditions[:2])
        lines.append(f"| {rank} | {item.symbol} | {item.name} | {item.score:.1f} | {logic} | {trigger} | {invalid} |")

    lines.extend(
        [
            "",
            "## Rotation Status",
            "",
            f"- Old sector: {overview.rotation_status.old_sector or 'N/A'}",
            f"- New sector: {overview.rotation_status.new_sector or 'N/A'}",
            f"- Rotation score: {overview.rotation_status.rotation_score:.1f}",
            f"- Reasons: {'; '.join(overview.rotation_status.reasons)}",
            f"- Risks: {'; '.join(overview.rotation_status.risks)}",
        ]
    )
    return "\n".join(lines) + "\n"
