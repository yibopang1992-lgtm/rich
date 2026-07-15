from __future__ import annotations

import re
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from ashare_agent.data_sources.akshare_provider import denormalize_symbol, is_limit_up, to_float
from ashare_agent.models import SectorSnapshot, SectorType, StockSnapshot


CN_TZ = ZoneInfo("Asia/Shanghai")
SINA_VAR_RE = re.compile(r'var hq_str_(?P<code>[a-z]{2}\d{6})="(?P<body>.*?)";')
SINA_SECTOR_RE = re.compile(r"var\s+S_Finance_bankuai_\w+\s*=\s*(?P<body>\{.*\})\s*;?\s*$", re.S)


def to_sina_code(symbol: str) -> str:
    raw = denormalize_symbol(symbol)
    suffix = symbol.split(".")[-1].upper()
    prefix = "sh" if suffix == "SH" else "sz"
    return f"{prefix}{raw}"


def from_sina_code(code: str) -> str:
    raw = code[-6:]
    suffix = "SH" if code.startswith("sh") else "SZ"
    return f"{raw}.{suffix}"


def fetch_sina_stock_snapshots(symbols: list[str], chunk_size: int = 200) -> list[StockSnapshot]:
    snapshots: list[StockSnapshot] = []
    cleaned_symbols = [symbol for symbol in dict.fromkeys(symbols) if symbol]
    for start in range(0, len(cleaned_symbols), chunk_size):
        chunk = cleaned_symbols[start : start + chunk_size]
        snapshots.extend(fetch_sina_stock_snapshot_chunk(chunk))
    return snapshots


def fetch_sina_sector_snapshots(as_of: datetime | None = None) -> list[SectorSnapshot]:
    timestamp = as_of or datetime.now(CN_TZ)
    rows: list[tuple[SectorType, dict[str, str]]] = []
    rows.extend((SectorType.INDUSTRY, row) for row in fetch_sina_sector_rows("industry"))
    rows.extend((SectorType.CONCEPT, row) for row in fetch_sina_sector_rows("concept"))

    snapshots: list[SectorSnapshot] = []
    for sector_type, row in rows:
        leader_code = row.get("leader_code", "")
        top_symbols = [from_sina_code(leader_code)] if leader_code.startswith(("sh", "sz")) else []
        snapshots.append(
            SectorSnapshot(
                sector_id=f"sina_{row['code']}",
                sector_name=row["name"],
                sector_type=sector_type,
                timestamp=timestamp,
                pct_change=to_float(row.get("pct_change")),
                main_net_inflow=0,
                amount=to_float(row.get("amount")),
                amount_growth=0,
                up_count=0,
                down_count=0,
                limit_up_count=0,
                limit_down_count=0,
                new_high_count=0,
                breadth=0.5,
                top_symbols=top_symbols,
                continuity_days=0,
                catalyst_strength=0,
                board_open_rate=0,
                tail_support=50,
            )
        )
    return snapshots


def fetch_sina_sector_memberships(sectors: list[SectorSnapshot]) -> list[dict[str, str]]:
    memberships: list[dict[str, str]] = []
    for sector in sectors:
        for symbol in sector.top_symbols:
            memberships.append(
                {
                    "sector_name": sector.sector_name,
                    "sector_type": sector.sector_type.value,
                    "symbol": symbol,
                    "name": "",
                }
            )
    return memberships


def fetch_sina_sector_rows(kind: str) -> list[dict[str, str]]:
    if kind == "industry":
        url = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
    elif kind == "concept":
        url = "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class"
    else:
        raise ValueError(f"unsupported Sina sector kind: {kind}")

    response = requests.get(
        url,
        headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    response.encoding = "gbk"
    match = SINA_SECTOR_RE.search(response.text)
    if not match:
        raise RuntimeError("Sina sector payload did not match expected JavaScript object")

    payload = json.loads(match.group("body"))
    parsed: list[dict[str, str]] = []
    for value in payload.values():
        fields = str(value).split(",")
        if len(fields) < 13:
            continue
        parsed.append(
            {
                "code": fields[0],
                "name": fields[1],
                "stock_count": fields[2],
                "avg_price": fields[3],
                "change": fields[4],
                "pct_change": fields[5],
                "volume": fields[6],
                "amount": fields[7],
                "leader_code": fields[8],
                "leader_pct_change": fields[9],
                "leader_price": fields[10],
                "leader_change": fields[11],
                "leader_name": fields[12],
            }
        )
    return parsed


def fetch_sina_stock_snapshot_chunk(symbols: list[str]) -> list[StockSnapshot]:
    if not symbols:
        return []
    sina_codes = [to_sina_code(symbol) for symbol in symbols]
    response = requests.get(
        "https://hq.sinajs.cn/list=" + ",".join(sina_codes),
        headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    response.encoding = "gbk"

    snapshots: list[StockSnapshot] = []
    for match in SINA_VAR_RE.finditer(response.text):
        code = match.group("code")
        fields = match.group("body").split(",")
        if len(fields) < 32 or not fields[0]:
            continue
        symbol = from_sina_code(code)
        open_price = to_float(fields[1])
        prev_close = to_float(fields[2])
        price = to_float(fields[3])
        high = to_float(fields[4])
        low = to_float(fields[5])
        volume = to_float(fields[8])
        amount = to_float(fields[9])
        trade_date = fields[30]
        trade_time = fields[31]
        timestamp = parse_sina_timestamp(trade_date, trade_time)
        pct_change = ((price - prev_close) / prev_close * 100) if prev_close else 0

        snapshots.append(
            StockSnapshot(
                symbol=symbol,
                name=fields[0],
                timestamp=timestamp,
                price=price,
                pct_change=pct_change,
                open=open_price,
                high=high,
                low=low,
                prev_close=prev_close,
                volume=volume,
                amount=amount,
                turnover_rate=0,
                main_net_inflow=0,
                large_order_net_inflow=0,
                super_large_order_net_inflow=0,
                limit_up=is_limit_up(symbol, pct_change),
                limit_down=pct_change <= -9.5,
            )
        )
    return snapshots


def parse_sina_timestamp(trade_date: str, trade_time: str) -> datetime:
    try:
        return datetime.fromisoformat(f"{trade_date}T{trade_time}").replace(tzinfo=CN_TZ)
    except ValueError:
        return datetime.now(CN_TZ)
