from __future__ import annotations

import math
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from ashare_agent.models import LimitUpEvent, NewsEvent, SectorSnapshot, SectorType, StockSnapshot


CN_TZ = ZoneInfo("Asia/Shanghai")


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and value.strip() in {"", "-", "--", "None", "nan"}:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    return int(to_float(value, default))


def normalize_symbol(code: Any) -> str:
    raw = str(code).strip().zfill(6)
    if raw.startswith(("6", "9")):
        return f"{raw}.SH"
    if raw.startswith(("8", "4")):
        return f"{raw}.BJ"
    return f"{raw}.SZ"


def is_supported_a_share_code(code: Any) -> bool:
    raw = str(code).strip().zfill(6)
    return raw.startswith(("0", "3", "6", "8", "4"))


def denormalize_symbol(symbol: str) -> str:
    return symbol.split(".")[0]


def first_present(row: Any, names: list[str], default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def is_limit_up(symbol: str, pct_change: float) -> bool:
    code = denormalize_symbol(symbol)
    threshold = 19.5 if code.startswith(("300", "301", "688")) else 9.5
    return pct_change >= threshold


def parse_hhmmss(value: Any) -> str:
    raw = str(value or "").strip().replace(":", "")
    if not raw or raw in {"-", "--"}:
        return ""
    raw = raw.zfill(6)
    return f"{raw[:2]}:{raw[2:4]}:{raw[4:6]}"


def fetch_stock_snapshots(as_of: datetime | None = None) -> list[StockSnapshot]:
    timestamp = as_of or datetime.now(CN_TZ)
    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        rows = df.to_dict("records")
    except Exception:
        rows = fetch_eastmoney_stock_rows()
    snapshots: list[StockSnapshot] = []
    for row in rows:
        symbol = normalize_symbol(first_present(row, ["代码", "code", "symbol"]))
        price = to_float(first_present(row, ["最新价", "最新", "price"]))
        pct_change = to_float(first_present(row, ["涨跌幅", "涨幅", "pct_change"]))
        prev_close = to_float(first_present(row, ["昨收", "prev_close"]), price / (1 + pct_change / 100) if pct_change != -100 else price)
        open_price = to_float(first_present(row, ["今开", "开盘", "open"]), price)
        high = to_float(first_present(row, ["最高", "high"]), price)
        low = to_float(first_present(row, ["最低", "low"]), price)
        volume = to_float(first_present(row, ["成交量", "volume"]))
        amount = to_float(first_present(row, ["成交额", "amount"]))
        snapshots.append(
            StockSnapshot(
                symbol=symbol,
                name=str(first_present(row, ["名称", "name"], "")),
                timestamp=timestamp,
                price=price,
                pct_change=pct_change,
                open=open_price,
                high=high,
                low=low,
                prev_close=prev_close,
                volume=volume,
                amount=amount,
                turnover_rate=to_float(first_present(row, ["换手率", "turnover_rate"])),
                main_net_inflow=to_float(first_present(row, ["主力净流入", "主力净额"])),
                large_order_net_inflow=to_float(first_present(row, ["大单净流入"])),
                super_large_order_net_inflow=to_float(first_present(row, ["超大单净流入"])),
                limit_up=is_limit_up(symbol, pct_change),
                limit_down=pct_change <= -9.5,
                recent_5d_gain=0,
                market_cap=to_float(first_present(row, ["总市值", "market_cap"])),
            )
        )
    return snapshots


def fetch_limit_up_events(trade_date: date, as_of: datetime | None = None) -> tuple[list[LimitUpEvent], list[NewsEvent]]:
    timestamp = as_of or datetime.combine(trade_date, time(15, 30), tzinfo=CN_TZ)
    import akshare as ak

    df = ak.stock_zt_pool_em(date=trade_date.strftime("%Y%m%d"))
    limit_events: list[LimitUpEvent] = []
    news_events: list[NewsEvent] = []
    for row in df.to_dict("records"):
        code = first_present(row, ["代码"])
        if not is_supported_a_share_code(code):
            continue
        symbol = normalize_symbol(code)
        name = str(first_present(row, ["名称"], symbol))
        sector_name = str(first_present(row, ["所属行业"], ""))
        first_time = parse_hhmmss(first_present(row, ["首次封板时间"]))
        boards = max(1, to_int(first_present(row, ["连板数"], 1), 1))
        sealed_amount = max(0.0, to_float(first_present(row, ["封板资金"])))
        board_open_count = max(0, to_int(first_present(row, ["炸板次数"])))
        limit_events.append(
            LimitUpEvent(
                symbol=symbol,
                name=name,
                sector_name=sector_name,
                timestamp=timestamp,
                first_limit_time=first_time,
                consecutive_boards=boards,
                sealed_amount=sealed_amount,
                board_open_count=board_open_count,
            )
        )
        title = f"{name}涨停，所属行业：{sector_name or '未知'}"
        content = (
            f"涨跌幅={to_float(first_present(row, ['涨跌幅'])):.2f}%, "
            f"连板数={boards}, 炸板次数={board_open_count}, "
            f"封板资金={sealed_amount:.0f}, 首次封板={first_time or '未知'}"
        )
        news_events.append(
            NewsEvent(
                event_id=f"limit_up_reason:{trade_date.isoformat()}:{symbol}",
                timestamp=timestamp,
                source="akshare_stock_zt_pool_em",
                title=title,
                content=content,
                symbols=[symbol],
                sectors=[sector_name] if sector_name else [],
                event_type="limit_up_reason",
                sentiment=0.6 if board_open_count == 0 else 0.3,
                importance=min(100.0, 45 + boards * 10 + sealed_amount / 100_000_000),
                is_confirmed=True,
            )
        )
    return limit_events, news_events


def fetch_dragon_tiger_events(trade_date: date, as_of: datetime | None = None) -> list[NewsEvent]:
    timestamp = as_of or datetime.combine(trade_date, time(18, 0), tzinfo=CN_TZ)
    import akshare as ak

    date_text = trade_date.strftime("%Y%m%d")
    df = ak.stock_lhb_detail_em(start_date=date_text, end_date=date_text)
    events: list[NewsEvent] = []
    for row in df.to_dict("records"):
        code = first_present(row, ["代码"])
        if not is_supported_a_share_code(code):
            continue
        symbol = normalize_symbol(code)
        name = str(first_present(row, ["名称"], symbol))
        reason = str(first_present(row, ["上榜原因"], ""))
        interpretation = str(first_present(row, ["解读"], ""))
        net_buy = to_float(first_present(row, ["龙虎榜净买额"]))
        turnover_ratio = to_float(first_present(row, ["成交额占总成交比"]))
        title = f"{name}龙虎榜：{interpretation or reason or '上榜'}"
        content = (
            f"上榜原因={reason}; 龙虎榜净买额={net_buy:.0f}; "
            f"龙虎榜成交额={to_float(first_present(row, ['龙虎榜成交额'])):.0f}; "
            f"成交额占总成交比={turnover_ratio:.2f}%; 换手率={to_float(first_present(row, ['换手率'])):.2f}%"
        )
        sentiment = 0.4 if net_buy > 0 else (-0.4 if net_buy < 0 else 0)
        events.append(
            NewsEvent(
                event_id=f"dragon_tiger:{trade_date.isoformat()}:{symbol}:{len(events) + 1}",
                timestamp=timestamp,
                source="akshare_stock_lhb_detail_em",
                title=title,
                content=content,
                symbols=[symbol],
                sectors=[],
                event_type="dragon_tiger",
                sentiment=sentiment,
                importance=min(100.0, 40 + abs(net_buy) / 50_000_000 + turnover_ratio),
                is_confirmed=True,
            )
        )
    return events


def fetch_sector_snapshots(as_of: datetime | None = None) -> list[SectorSnapshot]:
    timestamp = as_of or datetime.now(CN_TZ)
    try:
        import akshare as ak

        frames = [
            (SectorType.CONCEPT, ak.stock_board_concept_name_em().to_dict("records")),
            (SectorType.INDUSTRY, ak.stock_board_industry_name_em().to_dict("records")),
        ]
    except Exception:
        frames = [
            (SectorType.CONCEPT, fetch_eastmoney_sector_rows(SectorType.CONCEPT)),
            (SectorType.INDUSTRY, fetch_eastmoney_sector_rows(SectorType.INDUSTRY)),
        ]
    snapshots: list[SectorSnapshot] = []
    for sector_type, rows in frames:
        for row in rows:
            name = str(first_present(row, ["板块名称", "名称", "name"], ""))
            if not name:
                continue
            up_count = to_int(first_present(row, ["上涨家数", "上涨数"]))
            down_count = to_int(first_present(row, ["下跌家数", "下跌数"]))
            total_count = max(up_count + down_count, 1)
            leader_code = first_present(row, ["领涨股票代码", "领涨股票-代码", "代码"])
            top_symbols = [normalize_symbol(leader_code)] if leader_code else []
            snapshots.append(
                SectorSnapshot(
                    sector_id=f"{sector_type.value}_{name}",
                    sector_name=name,
                    sector_type=sector_type,
                    timestamp=timestamp,
                    pct_change=to_float(first_present(row, ["涨跌幅", "涨幅"])),
                    main_net_inflow=to_float(first_present(row, ["主力净流入", "净流入"])),
                    amount=to_float(first_present(row, ["成交额", "amount"])),
                    amount_growth=0,
                    up_count=up_count,
                    down_count=down_count,
                    limit_up_count=0,
                    limit_down_count=0,
                    new_high_count=0,
                    breadth=up_count / total_count,
                    top_symbols=top_symbols,
                    tail_support=50,
                )
            )
    return snapshots


def fetch_eastmoney_stock_rows() -> list[dict[str, Any]]:
    import requests

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1,
        "pz": 6000,
        "po": 1,
        "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18,f20,f8",
    }
    response = requests.get(url, params=params, headers=eastmoney_headers(), timeout=20)
    response.raise_for_status()
    data = response.json()
    rows = data.get("data", {}).get("diff") or []
    return [
        {
            "代码": row.get("f12"),
            "名称": row.get("f14"),
            "最新价": row.get("f2"),
            "涨跌幅": row.get("f3"),
            "涨跌额": row.get("f4"),
            "成交量": row.get("f5"),
            "成交额": row.get("f6"),
            "振幅": row.get("f7"),
            "最高": row.get("f15"),
            "最低": row.get("f16"),
            "今开": row.get("f17"),
            "昨收": row.get("f18"),
            "总市值": row.get("f20"),
            "换手率": row.get("f8"),
        }
        for row in rows
    ]


def fetch_eastmoney_sector_rows(sector_type: SectorType) -> list[dict[str, Any]]:
    import requests

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    market_filter = "m:90+t:3" if sector_type == SectorType.CONCEPT else "m:90+t:2"
    params = {
        "pn": 1,
        "pz": 500,
        "po": 1,
        "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": market_filter,
        "fields": "f12,f14,f3,f6,f62,f104,f105,f128,f140",
    }
    response = requests.get(url, params=params, headers=eastmoney_headers(), timeout=20)
    response.raise_for_status()
    data = response.json()
    rows = data.get("data", {}).get("diff") or []
    return [
        {
            "代码": row.get("f12"),
            "板块名称": row.get("f14"),
            "涨跌幅": row.get("f3"),
            "成交额": row.get("f6"),
            "主力净流入": row.get("f62"),
            "上涨家数": row.get("f104"),
            "下跌家数": row.get("f105"),
            "领涨股票": row.get("f128"),
            "领涨股票代码": row.get("f140"),
        }
        for row in rows
    ]


def eastmoney_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    }


def fetch_sector_memberships(
    sectors: list[SectorSnapshot],
    per_type_limit: int = 8,
) -> list[dict[str, str]]:
    import akshare as ak

    memberships: list[dict[str, str]] = []
    counts = {SectorType.CONCEPT: 0, SectorType.INDUSTRY: 0}
    sorted_sectors = sorted(sectors, key=lambda item: item.pct_change, reverse=True)

    for sector in sorted_sectors:
        if counts[sector.sector_type] >= per_type_limit:
            continue
        try:
            if sector.sector_type == SectorType.CONCEPT:
                df = ak.stock_board_concept_cons_em(symbol=sector.sector_name)
            else:
                df = ak.stock_board_industry_cons_em(symbol=sector.sector_name)
        except Exception:
            continue
        counts[sector.sector_type] += 1
        for row in df.to_dict("records"):
            code = first_present(row, ["代码", "股票代码", "symbol"])
            if not code:
                continue
            memberships.append(
                {
                    "sector_name": sector.sector_name,
                    "sector_type": sector.sector_type.value,
                    "symbol": normalize_symbol(code),
                    "name": str(first_present(row, ["名称", "股票名称", "name"], "")),
                }
            )
    return memberships
