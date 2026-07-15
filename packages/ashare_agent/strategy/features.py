from __future__ import annotations

from datetime import datetime

from ashare_agent.models import NewsEvent, StockFeature, StockSnapshot


def build_stock_features(
    stocks: list[StockSnapshot],
    moneyflow_rows: list[dict],
) -> tuple[list[StockFeature], list[NewsEvent]]:
    moneyflow_by_symbol = {row["symbol"]: row for row in moneyflow_rows}
    stock_by_symbol = {item.symbol: item for item in stocks}
    symbols = set(stock_by_symbol) | set(moneyflow_by_symbol)
    if not symbols:
        return [], []

    amount_ranked = sorted(
        (stock_by_symbol.get(symbol) for symbol in symbols if stock_by_symbol.get(symbol)),
        key=lambda item: item.amount,
        reverse=True,
    )
    flow_ranked = sorted(
        moneyflow_by_symbol.values(),
        key=lambda item: float(item.get("main_net_inflow") or 0),
        reverse=True,
    )
    amount_rank = {item.symbol: rank for rank, item in enumerate(amount_ranked, start=1)}
    flow_rank = {item["symbol"]: rank for rank, item in enumerate(flow_ranked, start=1)}
    amount_total = max(1, len(amount_ranked))
    flow_total = max(1, len(flow_ranked))

    features: list[StockFeature] = []
    rush_events: list[NewsEvent] = []
    for symbol in sorted(symbols):
        stock = stock_by_symbol.get(symbol)
        flow = moneyflow_by_symbol.get(symbol, {})
        name = str(flow.get("name") or (stock.name if stock else symbol))
        timestamp = _feature_timestamp(stock, flow)
        amount = float(stock.amount if stock else 0)
        main_net = float(flow.get("main_net_inflow") or (stock.main_net_inflow if stock else 0))
        pct_change = float(flow.get("pct_change") or (stock.pct_change if stock else 0))
        turnover = float(stock.turnover_rate if stock else 0)
        arank = amount_rank.get(symbol, 0)
        frank = flow_rank.get(symbol, 0)
        amount_percentile = _rank_percentile(arank, amount_total)
        flow_percentile = _rank_percentile(frank, flow_total)
        flow_to_amount = main_net / amount if amount > 0 else 0
        rush_score = _rush_accumulation_score(
            pct_change=pct_change,
            turnover_rate=turnover,
            amount_percentile=amount_percentile,
            flow_percentile=flow_percentile,
            flow_to_amount=flow_to_amount,
        )
        feature = StockFeature(
            symbol=symbol,
            name=name,
            timestamp=timestamp,
            pct_change=pct_change,
            amount=amount,
            turnover_rate=turnover,
            amount_rank=arank,
            amount_percentile=amount_percentile,
            main_net_inflow=main_net,
            main_net_inflow_rank=frank,
            main_net_inflow_percentile=flow_percentile,
            main_net_inflow_to_amount=flow_to_amount,
            rush_accumulation_score=rush_score,
            limit_up=bool(stock.limit_up) if stock else pct_change >= 9.5,
            limit_down=bool(stock.limit_down) if stock else pct_change <= -9.5,
            recent_5d_gain=float(stock.recent_5d_gain) if stock else 0,
            sector_names=list(stock.sector_names) if stock else [],
        )
        features.append(feature)
        if _is_rush_accumulation(feature):
            rush_events.append(
                NewsEvent(
                    event_id=f"rush_accumulation:{timestamp.date().isoformat()}:{symbol}",
                    timestamp=timestamp,
                    source="derived_stock_feature",
                    title=f"{name}出现抢筹特征",
                    content=(
                        f"抢筹分={rush_score:.1f}; 主力净流入={main_net:.0f}; "
                        f"主力净流入排名={frank}; 涨跌幅={pct_change:.2f}%; "
                        f"成交额分位={amount_percentile:.2f}; 净流入/成交额={flow_to_amount:.3f}"
                    ),
                    symbols=[symbol],
                    sectors=list(stock.sector_names) if stock else [],
                    event_type="rush_accumulation",
                    sentiment=0.5,
                    importance=rush_score,
                    is_confirmed=True,
                )
            )
    return sorted(features, key=lambda item: item.rush_accumulation_score, reverse=True), rush_events


def _feature_timestamp(stock: StockSnapshot | None, flow: dict) -> datetime:
    flow_as_of = flow.get("as_of")
    if flow_as_of:
        return datetime.fromisoformat(str(flow_as_of))
    if stock:
        return stock.timestamp
    return datetime.now().astimezone()


def _rank_percentile(rank: int, total: int) -> float:
    if rank <= 0 or total <= 0:
        return 0
    return max(0.0, min(1.0, 1 - (rank - 1) / total))


def _rush_accumulation_score(
    pct_change: float,
    turnover_rate: float,
    amount_percentile: float,
    flow_percentile: float,
    flow_to_amount: float,
) -> float:
    score = 100 * (0.42 * flow_percentile + 0.22 * amount_percentile)
    score += min(18.0, max(0.0, pct_change) * 2.0)
    score += min(10.0, max(0.0, turnover_rate) * 0.5)
    score += min(14.0, max(0.0, flow_to_amount) * 100)
    if pct_change < -2:
        score -= 12
    return round(max(0.0, min(100.0, score)), 2)


def _is_rush_accumulation(feature: StockFeature) -> bool:
    return (
        feature.rush_accumulation_score >= 78
        and feature.main_net_inflow > 0
        and feature.pct_change > 0
        and not feature.limit_down
    )
