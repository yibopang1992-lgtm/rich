from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from ashare_agent.data_sources.akshare_provider import is_limit_up, to_float
from ashare_agent.models import StockSnapshot


CN_TZ = ZoneInfo("Asia/Shanghai")


def normalize_baostock_symbol(code: str) -> str:
    market, raw = code.split(".")
    suffix = {"sh": "SH", "sz": "SZ", "bj": "BJ"}.get(market, market.upper())
    return f"{raw}.{suffix}"


def is_common_a_share(code: str) -> bool:
    return code.startswith(("sh.60", "sh.68", "sz.00", "sz.30", "bj."))


def fetch_baostock_daily_snapshots(
    trade_date: date,
    max_symbols: int | None = None,
) -> list[StockSnapshot]:
    import baostock as bs

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login.error_msg}")

    try:
        codes = load_stock_codes(bs, trade_date)
        if max_symbols is not None and max_symbols > 0:
            codes = codes[:max_symbols]

        timestamp = datetime.combine(trade_date, time(15, 0), tzinfo=CN_TZ)
        snapshots: list[StockSnapshot] = []
        for code, name in codes:
            rs = bs.query_history_k_data_plus(
                code,
                "date,code,open,high,low,close,preclose,volume,amount,pctChg,turn",
                start_date=trade_date.isoformat(),
                end_date=trade_date.isoformat(),
                frequency="d",
                adjustflag="3",
            )
            if rs.error_code != "0":
                continue
            while rs.next():
                row = dict(zip(rs.fields, rs.get_row_data(), strict=True))
                symbol = normalize_baostock_symbol(row["code"])
                pct_change = to_float(row.get("pctChg"))
                snapshots.append(
                    StockSnapshot(
                        symbol=symbol,
                        name=name,
                        timestamp=timestamp,
                        price=to_float(row.get("close")),
                        pct_change=pct_change,
                        open=to_float(row.get("open")),
                        high=to_float(row.get("high")),
                        low=to_float(row.get("low")),
                        prev_close=to_float(row.get("preclose")),
                        volume=to_float(row.get("volume")),
                        amount=to_float(row.get("amount")),
                        turnover_rate=to_float(row.get("turn")),
                        main_net_inflow=0,
                        large_order_net_inflow=0,
                        super_large_order_net_inflow=0,
                        limit_up=is_limit_up(symbol, pct_change),
                        limit_down=pct_change <= -9.5,
                        recent_5d_gain=0,
                        market_cap=0,
                    )
                )
        return snapshots
    finally:
        bs.logout()


def fetch_baostock_daily_snapshots_range(
    start_date: date,
    end_date: date,
    max_symbols: int | None = None,
) -> list[StockSnapshot]:
    import baostock as bs

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login.error_msg}")

    try:
        codes = load_stock_codes(bs, end_date)
        if max_symbols is not None and max_symbols > 0:
            codes = codes[:max_symbols]

        names_by_code = dict(codes)
        snapshots: list[StockSnapshot] = []
        for code, name in names_by_code.items():
            rs = bs.query_history_k_data_plus(
                code,
                "date,code,open,high,low,close,preclose,volume,amount,pctChg,turn",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                frequency="d",
                adjustflag="3",
            )
            if rs.error_code != "0":
                continue
            while rs.next():
                row = dict(zip(rs.fields, rs.get_row_data(), strict=True))
                symbol = normalize_baostock_symbol(row["code"])
                pct_change = to_float(row.get("pctChg"))
                trade_date = date.fromisoformat(row["date"])
                snapshots.append(
                    StockSnapshot(
                        symbol=symbol,
                        name=name,
                        timestamp=datetime.combine(trade_date, time(15, 0), tzinfo=CN_TZ),
                        price=to_float(row.get("close")),
                        pct_change=pct_change,
                        open=to_float(row.get("open")),
                        high=to_float(row.get("high")),
                        low=to_float(row.get("low")),
                        prev_close=to_float(row.get("preclose")),
                        volume=to_float(row.get("volume")),
                        amount=to_float(row.get("amount")),
                        turnover_rate=to_float(row.get("turn")),
                        main_net_inflow=0,
                        large_order_net_inflow=0,
                        super_large_order_net_inflow=0,
                        limit_up=is_limit_up(symbol, pct_change),
                        limit_down=pct_change <= -9.5,
                        recent_5d_gain=0,
                        market_cap=0,
                    )
                )
        return snapshots
    finally:
        bs.logout()


def load_stock_codes(bs, trade_date: date) -> list[tuple[str, str]]:
    rs = bs.query_all_stock(day=trade_date.isoformat())
    if rs.error_code != "0":
        raise RuntimeError(f"baostock query_all_stock failed: {rs.error_msg}")

    codes: list[tuple[str, str]] = []
    while rs.next():
        row = rs.get_row_data()
        code = row[0]
        name = row[2] if len(row) >= 3 else code
        if is_common_a_share(code):
            codes.append((code, name))
    return codes
