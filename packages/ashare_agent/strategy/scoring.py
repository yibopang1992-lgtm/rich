from __future__ import annotations

from statistics import median

from ashare_agent.data_sources.base import MarketDataProvider
from ashare_agent.models import (
    BacktestResult,
    BacktestTrade,
    CandidateTier,
    CatchupCandidate,
    LeaderCandidate,
    MainlineScore,
    MarketOverview,
    RotationStatus,
    SectorSnapshot,
    SectorStage,
    StockRole,
    StockSnapshot,
)


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def normalize_signed(value: float, scale: float) -> float:
    return clamp(50 + (value / scale) * 50)


def score_sector(sector: SectorSnapshot) -> MainlineScore:
    has_fund_flow = sector.main_net_inflow != 0
    fund_flow_strength = normalize_signed(sector.main_net_inflow, 12_000_000_000)
    amount_growth = clamp(sector.amount_growth * 100)
    sector_return = normalize_signed(sector.pct_change, 8)
    limit_up_ladder = clamp(sector.limit_up_count * 12 + sector.new_high_count * 2)
    breadth = clamp(sector.breadth * 100)
    leader_strength = clamp(35 + sector.limit_up_count * 7 + sector.continuity_days * 6)
    continuity = clamp(sector.continuity_days * 25)
    catalyst_strength = sector.catalyst_strength

    score = (
        0.20 * fund_flow_strength
        + 0.15 * amount_growth
        + 0.15 * sector_return
        + 0.15 * limit_up_ladder
        + 0.10 * breadth
        + 0.10 * leader_strength
        + 0.10 * continuity
        + 0.05 * catalyst_strength
    )

    if not has_fund_flow and sector.amount > 0 and sector.limit_up_count == 0:
        # Sina sector data has price/amount/leader fields but no fund-flow or limit-up ladder.
        # Keep it useful for heat ranking while marking fund-flow confirmation as missing.
        liquidity = clamp(sector.amount / 50_000_000_000 * 100)
        heat_score = 0.45 * sector_return + 0.35 * liquidity + 0.20 * breadth
        score = min(max(score, heat_score), 79)

    score = round(clamp(score), 2)

    if score >= 80:
        tier = "strong_mainline"
    elif score >= 65:
        tier = "candidate_mainline"
    elif score >= 50:
        tier = "rotation_hotspot"
    else:
        tier = "weak"
    if not has_fund_flow and tier in {"strong_mainline", "candidate_mainline"}:
        tier = "rotation_hotspot"

    stage = classify_stage(sector)
    reasons = [
        f"sector return {sector.pct_change:.2f}%",
        (
            f"net inflow {sector.main_net_inflow / 100_000_000:.1f}e CNY"
            if has_fund_flow
            else "net inflow unavailable"
        ),
        f"breadth {sector.breadth:.1%}",
        f"{sector.limit_up_count} limit-up symbols",
    ]
    risks: list[str] = []
    if sector.board_open_rate >= 0.35:
        risks.append("board-open rate is elevated")
    if stage in {SectorStage.CLIMAX, SectorStage.DIVERGENCE, SectorStage.FADING}:
        risks.append(f"sector stage is {stage.value}")
    if sector.tail_support < 50:
        risks.append("tail support is weak")
    if not has_fund_flow and sector.amount > 0:
        risks.append("fund-flow data is unavailable; score uses price/amount heat")

    return MainlineScore(
        sector_name=sector.sector_name,
        score=score,
        stage=stage,
        tier=tier,
        reasons=reasons,
        risks=risks,
        as_of=sector.timestamp,
    )


def classify_stage(sector: SectorSnapshot) -> SectorStage:
    if sector.main_net_inflow < 0 and sector.limit_up_count <= 1 and sector.breadth < 0.4:
        return SectorStage.FADING
    if sector.board_open_rate >= 0.4 or (
        sector.pct_change < 0 and sector.limit_up_count > 0 and sector.breadth < 0.5
    ):
        return SectorStage.DIVERGENCE
    if sector.limit_up_count >= 7 and sector.pct_change >= 5 and sector.breadth >= 0.8:
        return SectorStage.CLIMAX
    if sector.limit_up_count >= 4 and sector.continuity_days >= 2 and sector.breadth >= 0.65:
        return SectorStage.MARKUP
    if sector.limit_up_count >= 2 and sector.main_net_inflow > 0 and sector.breadth >= 0.55:
        return SectorStage.FERMENTING
    return SectorStage.STARTING


def find_leaders(provider: MarketDataProvider, max_items: int = 5) -> list[LeaderCandidate]:
    sectors = {sector.sector_name: sector for sector in provider.get_sector_snapshots()}
    candidates: list[LeaderCandidate] = []

    for stock in provider.get_stock_snapshots():
        matched_sectors = [name for name in stock.sector_names if name in sectors]
        if not matched_sectors:
            continue
        sector_name = matched_sectors[0]
        score = clamp(
            35
            + stock.pct_change * 1.8
            + min(stock.amount / 1_000_000_000, 12) * 2
            + (18 if stock.limit_up else 0)
            + min(stock.sealed_amount / 100_000_000, 15)
            - stock.board_open_count * 4
        )
        if stock.limit_up and stock.pct_change >= 9.5:
            role = StockRole.SENTIMENT_LEADER
        elif stock.market_cap >= 80_000_000_000 and stock.amount >= 5_000_000_000:
            role = StockRole.TREND_ANCHOR
        elif stock.symbol.startswith("300") and stock.pct_change >= 10:
            role = StockRole.TWENTY_CM_CORE
        else:
            role = StockRole.FOLLOWER

        risks: list[str] = []
        if stock.recent_5d_gain >= 30:
            risks.append("recent 5-day gain is high; chasing risk is elevated")
        if stock.board_open_count >= 2:
            risks.append("multiple board opens indicate disagreement")

        candidates.append(
            LeaderCandidate(
                symbol=stock.symbol,
                name=stock.name,
                sector_name=sector_name,
                role=role,
                score=round(score, 2),
                reasons=[
                    f"pct change {stock.pct_change:.2f}%",
                    f"amount {stock.amount / 100_000_000:.1f}e CNY",
                    f"main inflow {stock.main_net_inflow / 100_000_000:.1f}e CNY",
                ],
                risks=risks,
                as_of=stock.timestamp,
            )
        )

    return sorted(candidates, key=lambda item: item.score, reverse=True)[:max_items]


def find_catchup_candidates(
    provider: MarketDataProvider,
    sector_names: list[str] | None = None,
    max_candidates: int = 5,
    exclude_limit_up: bool = True,
    max_recent_5d_gain: float = 20,
) -> list[CatchupCandidate]:
    mainlines = {score.sector_name: score for score in score_mainlines(provider)}
    selected = set(sector_names or mainlines.keys())
    candidates: list[CatchupCandidate] = []

    for stock in provider.get_stock_snapshots():
        matched_sector = next((name for name in stock.sector_names if name in selected), None)
        if matched_sector is None:
            continue
        if exclude_limit_up and stock.limit_up:
            continue
        if stock.recent_5d_gain > max_recent_5d_gain:
            continue
        has_money_flow = stock.main_net_inflow > 0
        min_amount = 800_000_000 if has_money_flow else 300_000_000
        if stock.amount < min_amount:
            continue
        if not (0.5 <= stock.pct_change <= 8):
            continue

        mainline = mainlines.get(matched_sector)
        if mainline and mainline.tier == "weak":
            continue
        mainline_purity = mainline.score if mainline else 50
        fresh_capital = (
            clamp(stock.main_net_inflow / max(stock.amount, 1) * 600)
            if has_money_flow
            else clamp(stock.amount / 2_000_000_000 * 75)
        )
        position_advantage = clamp(100 - stock.recent_5d_gain * 3)
        amount_expansion = clamp(stock.amount / 3_000_000_000 * 80)
        diffusion_match = clamp(50 + (mainline.score - 50 if mainline else 0))
        historical_catchup = 62
        next_day_premium = 58
        lhb_preference = 50
        risk_penalty = estimate_risk_penalty(stock, mainline.stage if mainline else None)

        score = (
            0.20 * mainline_purity
            + 0.15 * fresh_capital
            + 0.15 * position_advantage
            + 0.10 * amount_expansion
            + 0.10 * diffusion_match
            + 0.10 * historical_catchup
            + 0.10 * next_day_premium
            + 0.05 * lhb_preference
            - 0.05 * risk_penalty
        )
        score = round(clamp(score), 2)
        if not has_money_flow:
            score = min(score, 78)

        if score >= 85:
            tier = CandidateTier.CORE
        elif score >= 75:
            tier = CandidateTier.WATCH
        elif score >= 65:
            tier = CandidateTier.BACKUP
        else:
            tier = CandidateTier.REJECTED

        risks = []
        if stock.pct_change > 6:
            risks.append("intraday gain is near the upper bound for catch-up entry")
        if mainline and mainline.stage == SectorStage.CLIMAX:
            risks.append("sector is in climax; next-day consistency risk is higher")
        if stock.recent_5d_gain > 15:
            risks.append("recent gain is close to the filter threshold")
        if not has_money_flow:
            risks.append("money-flow data is unavailable; candidate is based on amount heat")

        candidates.append(
            CatchupCandidate(
                symbol=stock.symbol,
                name=stock.name,
                sector_name=matched_sector,
                score=score,
                tier=tier,
                role=f"{matched_sector} second-tier catch-up",
                reasons=[
                    (
                        f"belongs to active mainline {matched_sector}"
                        if has_money_flow
                        else f"belongs to active heat sector {matched_sector}"
                    ),
                    (
                        f"main inflow {stock.main_net_inflow / 100_000_000:.1f}e CNY"
                        if has_money_flow
                        else "main inflow unavailable"
                    ),
                    f"recent 5-day gain {stock.recent_5d_gain:.1f}% is not accelerated",
                    f"amount {stock.amount / 100_000_000:.1f}e CNY supports liquidity",
                ],
                risks=risks,
                trigger_conditions=[
                    (
                        "sector remains top-ranked by score or fund flow"
                        if has_money_flow
                        else "sector remains top-ranked by amount/price heat"
                    ),
                    (
                        "stock holds above intraday VWAP with positive net inflow"
                        if has_money_flow
                        else "stock holds above intraday VWAP with sustained turnover"
                    ),
                    "leader does not break down sharply",
                ],
                invalid_conditions=[
                    (
                        "sector fund flow turns negative"
                        if has_money_flow
                        else "sector amount heat falls out of the top group"
                    ),
                    "stock opens too high and fails to hold VWAP",
                    "leader breaks down or rear symbols show no premium",
                    "new risk announcement appears after close",
                ],
                as_of=stock.timestamp,
            )
        )

    actionable = [item for item in candidates if item.tier != CandidateTier.REJECTED]
    return sorted(actionable, key=lambda item: item.score, reverse=True)[:max_candidates]


def estimate_risk_penalty(stock: StockSnapshot, stage: SectorStage | None) -> float:
    penalty = 0.0
    if stock.recent_5d_gain > 15:
        penalty += 25
    if stock.pct_change > 6:
        penalty += 15
    if stage == SectorStage.CLIMAX:
        penalty += 20
    if stock.turnover_rate > 15:
        penalty += 10
    return clamp(penalty)


def score_mainlines(provider: MarketDataProvider) -> list[MainlineScore]:
    return sorted(
        [score_sector(sector) for sector in provider.get_sector_snapshots()],
        key=lambda item: item.score,
        reverse=True,
    )


def get_rotation_status(provider: MarketDataProvider) -> RotationStatus:
    mainlines = score_mainlines(provider)
    if len(mainlines) < 2:
        as_of = mainlines[0].as_of if mainlines else provider.get_sector_snapshots()[0].timestamp
        return RotationStatus(
            old_sector=None,
            new_sector=mainlines[0].sector_name if mainlines else None,
            rotation_score=0,
            is_confirmed=False,
            reasons=["insufficient sector universe"],
            risks=["rotation cannot be evaluated"],
            as_of=as_of,
        )

    new_sector = mainlines[0]
    old_sector = mainlines[-1]
    score_gap = clamp(new_sector.score - old_sector.score)
    rotation_score = round(clamp(score_gap + (20 if old_sector.stage == SectorStage.FADING else 0)), 2)
    is_confirmed = rotation_score >= 70 and new_sector.stage in {
        SectorStage.FERMENTING,
        SectorStage.MARKUP,
        SectorStage.CLIMAX,
    }

    return RotationStatus(
        old_sector=old_sector.sector_name,
        new_sector=new_sector.sector_name,
        rotation_score=rotation_score,
        is_confirmed=is_confirmed,
        reasons=[
            f"{new_sector.sector_name} score leads at {new_sector.score:.1f}",
            f"{old_sector.sector_name} score lags at {old_sector.score:.1f}",
        ],
        risks=[
            "rotation needs next-session confirmation",
            "free data source has limited tail-ladder depth",
        ],
        as_of=new_sector.as_of,
    )


def get_market_overview(provider: MarketDataProvider) -> MarketOverview:
    mainlines = score_mainlines(provider)
    leaders = find_leaders(provider)
    catchups = find_catchup_candidates(
        provider,
        sector_names=[item.sector_name for item in mainlines[:2]],
        max_candidates=5,
    )
    sentiment = "strong" if mainlines and mainlines[0].score >= 80 else "neutral"
    return MarketOverview(
        as_of=mainlines[0].as_of,
        data_mode="mock",
        market_sentiment=sentiment,
        mainlines=mainlines,
        leaders=leaders,
        catchup_candidates=catchups,
        rotation_status=get_rotation_status(provider),
    )


def run_mock_backtest(provider: MarketDataProvider) -> BacktestResult:
    candidates = find_catchup_candidates(provider, max_candidates=10)
    trades: list[BacktestTrade] = []
    for index, candidate in enumerate(candidates):
        base = (candidate.score - 65) / 100
        next_day = round(base * 7 - index * 0.6, 2)
        two_day = round(next_day + 1.8, 2)
        three_day = round(two_day - 0.7, 2)
        drawdown = round(-max(1.8, 6 - base * 10 + index * 0.4), 2)
        trades.append(
            BacktestTrade(
                symbol=candidate.symbol,
                name=candidate.name,
                sector_name=candidate.sector_name,
                signal_date=candidate.as_of,
                entry_return=0,
                next_day_close_return=next_day,
                two_day_high_return=two_day,
                three_day_high_return=three_day,
                max_drawdown=drawdown,
                stopped_out=drawdown <= -5,
            )
        )

    returns = [trade.next_day_close_return for trade in trades]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value <= 0]
    payoff_ratio = (
        round((sum(wins) / len(wins)) / abs(sum(losses) / len(losses)), 2)
        if wins and losses
        else 0
    )
    return BacktestResult(
        as_of=provider.get_sector_snapshots()[0].timestamp,
        sample_size=len(trades),
        win_rate=round(len(wins) / len(trades), 4) if trades else 0,
        average_return=round(sum(returns) / len(returns), 2) if returns else 0,
        median_return=round(median(returns), 2) if returns else 0,
        payoff_ratio=payoff_ratio,
        max_drawdown=min((trade.max_drawdown for trade in trades), default=0),
        trades=trades,
    )
