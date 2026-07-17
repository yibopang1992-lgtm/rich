from __future__ import annotations

from statistics import median

from ashare_agent.data_sources.base import MarketDataProvider
from ashare_agent.models import (
    BacktestResult,
    BacktestTrade,
    CandidateTier,
    CatchupCandidate,
    HighLowSwitchSignal,
    LeaderCandidate,
    MainlineScore,
    MarketOverview,
    RotationStatus,
    SectorSnapshot,
    SectorStage,
    SectorLimitupLinkage,
    StockRole,
    StockSnapshot,
)


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def normalize_signed(value: float, scale: float) -> float:
    return clamp(50 + (value / scale) * 50)


def score_sector(sector: SectorSnapshot) -> MainlineScore:
    has_fund_flow = sector.main_net_inflow != 0
    has_breadth = sector.up_count + sector.down_count > 0
    has_ladder = sector.limit_up_count > 0 or sector.new_high_count > 0 or sector.continuity_days > 0
    fund_flow_strength = normalize_signed(sector.main_net_inflow, 12_000_000_000)
    amount_growth = clamp(sector.amount_growth * 100)
    sector_return = normalize_signed(sector.pct_change, 8)
    limit_up_ladder = clamp(sector.limit_up_count * 12 + sector.new_high_count * 2)
    breadth = clamp(sector.breadth * 100) if has_breadth else 50
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

    if has_fund_flow and sector.amount == 0 and not has_ladder:
        # Eastmoney/InStock fund-flow rankings do not include breadth or ladder
        # fields. Treat them as fund-flow heat, not a full ladder-confirmed mainline.
        flow_heat_score = 0.58 * fund_flow_strength + 0.34 * sector_return + 0.08 * leader_strength
        score = min(max(score, flow_heat_score), 79)

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
        f"breadth {sector.breadth:.1%}" if has_breadth else "breadth unavailable",
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
    if has_fund_flow and not has_breadth:
        risks.append("breadth data is unavailable; score uses fund-flow/return heat")
    if has_fund_flow and not has_ladder:
        risks.append("limit-up ladder is unavailable in sector fund-flow rows")

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
    has_breadth = sector.up_count + sector.down_count > 0
    has_ladder = sector.limit_up_count > 0 or sector.new_high_count > 0 or sector.continuity_days > 0
    if not has_ladder:
        if sector.main_net_inflow < 0 and sector.pct_change < 0:
            return SectorStage.FADING
        if sector.main_net_inflow > 0 and (sector.pct_change >= 3 or sector.main_net_inflow >= 500_000_000):
            return SectorStage.FERMENTING
        if sector.main_net_inflow > 0 and sector.pct_change > 0:
            return SectorStage.STARTING
        if sector.main_net_inflow < 0 and sector.pct_change <= 0:
            return SectorStage.FADING
        return SectorStage.STARTING
    if has_breadth and sector.main_net_inflow < 0 and sector.limit_up_count <= 1 and sector.breadth < 0.4:
        return SectorStage.FADING
    if sector.board_open_rate >= 0.4 or (has_breadth and
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


def analyze_limitup_linkage(
    provider: MarketDataProvider,
    min_sector_limitups: int = 3,
    min_market_limitups: int = 30,
    max_items: int = 10,
) -> list[SectorLimitupLinkage]:
    events = provider.get_limit_up_events()
    if not events:
        return []

    by_sector: dict[str, list] = {}
    for event in events:
        sector_name = event.sector_name or "未分类"
        if not is_pure_strategy_sector_name(sector_name):
            continue
        by_sector.setdefault(sector_name, []).append(event)

    market_is_warm = len(events) >= min_market_limitups
    results: list[SectorLimitupLinkage] = []
    for sector_name, sector_events in by_sector.items():
        ordered = sorted(
            sector_events,
            key=lambda item: (
                -item.consecutive_boards,
                _parse_limit_time(item.first_limit_time),
                -item.sealed_amount,
            ),
        )
        leader = ordered[0]
        followers = [item.symbol for item in ordered[1:]]
        limit_up_count = len(sector_events)
        linkage_strength = clamp(limit_up_count / max(min_sector_limitups, 1) * 70)
        leader_bonus = clamp(leader.consecutive_boards * 8 + leader.sealed_amount / 200_000_000)
        market_bonus = 10 if market_is_warm else 0
        score = round(clamp(linkage_strength + leader_bonus + market_bonus), 2)
        is_linked = limit_up_count >= min_sector_limitups
        risks: list[str] = []
        if not market_is_warm:
            risks.append(f"全市场涨停家数 {len(events)} 低于 {min_market_limitups}，联动可靠性下降")
        if leader.board_open_count > 0:
            risks.append("候选龙头存在开板，合力不够纯")
        if limit_up_count >= 7:
            risks.append("板块涨停过多，次日一致性兑现风险升高")
        if not is_linked:
            risks.append("同板块涨停数未达到联动阈值")

        results.append(
            SectorLimitupLinkage(
                sector_name=sector_name,
                limit_up_count=limit_up_count,
                is_linked=is_linked,
                leader_symbol=leader.symbol,
                leader_name=leader.name,
                follower_symbols=followers,
                score=score,
                reasons=[
                    f"同板块涨停 {limit_up_count} 只",
                    f"仅标一只龙头：{leader.name}({leader.symbol})",
                    f"龙头连板数 {leader.consecutive_boards}，首次封板 {leader.first_limit_time or '未知'}",
                ],
                risks=risks,
                trigger_conditions=[
                    "次日龙头保持溢价或快速修复",
                    "板块内跟风股不批量低开破位",
                    "新热点没有明显分流涨停梯队",
                ],
                invalid_conditions=[
                    "龙头低开低走或高开无法承接",
                    "同板块后排无溢价并出现批量炸板",
                    "全市场涨停家数明显萎缩",
                ],
                as_of=leader.timestamp,
            )
        )

    return sorted(results, key=lambda item: item.score, reverse=True)[:max_items]


def find_high_low_switch_signals(
    provider: MarketDataProvider,
    sector_names: list[str] | None = None,
    max_candidates: int = 8,
) -> list[HighLowSwitchSignal]:
    mainlines = {score.sector_name: score for score in score_mainlines(provider)}
    linked_sectors = {item.sector_name: item for item in analyze_limitup_linkage(provider, min_market_limitups=0)}
    selected = set(sector_names or mainlines.keys())
    stocks = provider.get_stock_snapshots()
    if not stocks:
        return []

    signals: list[HighLowSwitchSignal] = []
    for stock in stocks:
        matched_sector = next((name for name in stock.sector_names if name in selected), None)
        if matched_sector is None:
            continue
        mainline = mainlines.get(matched_sector)
        if mainline and mainline.tier == "weak":
            continue
        if stock.limit_up or stock.recent_5d_gain > 12:
            continue

        is_low_position = stock.recent_5d_gain <= 5 and stock.pct_change <= 6
        avoids_middle = stock.recent_5d_gain <= 12 and stock.market_cap <= 80_000_000_000
        if not (is_low_position and avoids_middle):
            continue

        market_cap_score = clamp(100 - stock.market_cap / 800_000_000)
        low_price_score = clamp(100 - abs(stock.price - 10) * 8) if stock.price > 0 else 45
        low_position_score = clamp(100 - stock.recent_5d_gain * 8)
        flow_score = (
            clamp(stock.main_net_inflow / max(stock.amount, 1) * 700)
            if stock.main_net_inflow > 0
            else clamp(stock.amount / 2_000_000_000 * 45)
        )
        sector_score = mainline.score if mainline else 50
        linkage_score = linked_sectors.get(matched_sector).score if matched_sector in linked_sectors else 45
        score = round(
            clamp(
                0.22 * sector_score
                + 0.20 * low_position_score
                + 0.16 * market_cap_score
                + 0.14 * low_price_score
                + 0.14 * flow_score
                + 0.14 * linkage_score
            ),
            2,
        )
        if stock.main_net_inflow <= 0:
            score = min(score, 72)

        if score >= 82:
            tier = CandidateTier.CORE
        elif score >= 72:
            tier = CandidateTier.WATCH
        elif score >= 62:
            tier = CandidateTier.BACKUP
        else:
            tier = CandidateTier.REJECTED

        risks: list[str] = []
        if not mainline:
            risks.append("板块主线评分缺失，只能作为低位观察")
        elif mainline.stage in {SectorStage.CLIMAX, SectorStage.DIVERGENCE, SectorStage.FADING}:
            risks.append(f"板块处于 {mainline.stage.value}，低位补涨容易被高位亏钱效应拖累")
        if stock.main_net_inflow <= 0:
            risks.append("缺少主力净流入确认，当前为量价热度候选")
        if stock.price > 20 or stock.market_cap > 50_000_000_000:
            risks.append("价格或市值不完全符合小盘低价偏好")

        signals.append(
            HighLowSwitchSignal(
                symbol=stock.symbol,
                name=stock.name,
                sector_name=matched_sector,
                score=score,
                tier=tier,
                role=f"{matched_sector} low-position high-low-switch candidate",
                preconditions=[
                    "主线或候选主线仍有资金认可",
                    "高位/中位出现分歧时，只观察绝对低位补涨",
                    "中位股接力和已加速后排全部回避",
                ],
                reasons=[
                    f"近5日涨幅 {stock.recent_5d_gain:.1f}%，未加速",
                    f"市值 {stock.market_cap / 100_000_000:.1f} 亿，价格 {stock.price:.2f}",
                    f"成交额 {stock.amount / 100_000_000:.1f} 亿",
                    (
                        f"主力净流入 {stock.main_net_inflow / 100_000_000:.1f} 亿"
                        if stock.main_net_inflow > 0
                        else "主力净流入缺失或未转正"
                    ),
                ],
                risks=risks,
                trigger_conditions=[
                    "总龙头分歧后，主线没有整体退潮",
                    "低位标的弱转强并快速封板或持续站上 VWAP",
                    "同板块低位梯队出现扩散而不是单票脉冲",
                ],
                invalid_conditions=[
                    "总龙头 A 杀并拖累全板块",
                    "中位股继续批量亏钱，低位无封板确认",
                    "新主线吸走资金，原主线后排无溢价",
                ],
                as_of=stock.timestamp,
            )
        )

    actionable = [item for item in signals if item.tier != CandidateTier.REJECTED]
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


def _parse_limit_time(value: str) -> int:
    raw = (value or "99:99:99").replace(":", "")
    try:
        return int(raw)
    except ValueError:
        return 999999


def score_mainlines(provider: MarketDataProvider) -> list[MainlineScore]:
    return sorted(
        [score_sector(sector) for sector in provider.get_sector_snapshots() if is_pure_strategy_sector_name(sector.sector_name)],
        key=lambda item: item.score,
        reverse=True,
    )


def is_pure_strategy_sector_name(name: str) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    noisy_keywords = [
        "昨日",
        "今日",
        "近期",
        "首板",
        "连板",
        "打板",
        "炸板",
        "涨停",
        "触板",
        "龙虎榜",
        "融资融券",
        "沪股通",
        "深股通",
        "含一字",
        "高送转",
        "预盈预增",
        "一季报",
        "三季报",
        "中报",
        "年报",
        "扭亏",
        "预减",
        "预降",
        "预升",
        "破净",
        "破发",
        "破增发",
        "红利",
        "价值股",
        "超跌",
        "微盘",
        "微利",
        "B股",
        "AB股",
        "含H股",
        "含GDR",
        "风格",
        "大盘",
        "中盘",
        "小盘",
        "权重",
        "周期股",
        "趋势股",
        "题材股",
        "行业龙头",
        "历史新高",
        "百日新高",
        "最近多板",
        "东方财富热股",
    ]
    return not any(keyword in text for keyword in noisy_keywords)


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
