from __future__ import annotations

import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from ashare_agent.data_sources.akshare_provider import to_float
from ashare_agent.models import SectorSnapshot, SectorType, StockSnapshot


CN_TZ = ZoneInfo("Asia/Shanghai")


def require_tushare_token() -> str:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is not set")
    return token


def tushare_api():
    import tushare as ts

    return ts.pro_api(require_tushare_token())


def fetch_tushare_sector_fund_flow(trade_date: date) -> list[SectorSnapshot]:
    pro = tushare_api()
    timestamp = datetime.combine(trade_date, time(17, 0), tzinfo=CN_TZ)
    df = pro.moneyflow_ind_dc(
        trade_date=trade_date.strftime("%Y%m%d"),
        fields="trade_date,name,pct_change,close,net_amount,net_amount_rate,rank",
    )
    snapshots: list[SectorSnapshot] = []
    for row in df.to_dict("records"):
        name = str(row.get("name") or "")
        if not name:
            continue
        snapshots.append(
            SectorSnapshot(
                sector_id=f"tushare_dc_{name}",
                sector_name=name,
                sector_type=SectorType.CONCEPT,
                timestamp=timestamp,
                pct_change=to_float(row.get("pct_change")),
                main_net_inflow=to_float(row.get("net_amount")),
                amount=0,
                amount_growth=0,
                up_count=0,
                down_count=0,
                limit_up_count=0,
                limit_down_count=0,
                new_high_count=0,
                breadth=0.5,
                top_symbols=[],
                continuity_days=0,
                catalyst_strength=0,
                board_open_rate=0,
                tail_support=50,
            )
        )
    return snapshots


def fetch_tushare_stock_moneyflow(trade_date: date) -> list[StockSnapshot]:
    pro = tushare_api()
    timestamp = datetime.combine(trade_date, time(17, 0), tzinfo=CN_TZ)
    df = pro.moneyflow_ths(
        trade_date=trade_date.strftime("%Y%m%d"),
        fields=(
            "trade_date,ts_code,name,pct_change,latest,net_amount,net_d5_amount,"
            "buy_lg_amount,buy_lg_amount_rate,buy_md_amount,buy_md_amount_rate,"
            "buy_sm_amount,buy_sm_amount_rate"
        ),
    )
    snapshots: list[StockSnapshot] = []
    for row in df.to_dict("records"):
        symbol = str(row.get("ts_code") or "")
        if not symbol:
            continue
        main_net = to_float(row.get("net_amount")) * 10_000
        large_net = to_float(row.get("buy_lg_amount")) * 10_000
        snapshots.append(
            StockSnapshot(
                symbol=symbol,
                name=str(row.get("name") or symbol),
                timestamp=timestamp,
                price=to_float(row.get("latest")),
                pct_change=to_float(row.get("pct_change")),
                open=0,
                high=0,
                low=0,
                prev_close=0,
                volume=0,
                amount=0,
                turnover_rate=0,
                main_net_inflow=main_net,
                large_order_net_inflow=large_net,
                super_large_order_net_inflow=0,
            )
        )
    return snapshots
