from __future__ import annotations

import json
import math
import os
import random
import time
from datetime import date, datetime, time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ashare_agent.data_sources.akshare_provider import normalize_symbol, to_float
from ashare_agent.models import SectorSnapshot, SectorType, StockSnapshot


CN_TZ = ZoneInfo("Asia/Shanghai")


class EastmoneySession:
    """Small Eastmoney client adapted from InStock without its DB/Web/trade stack."""

    def __init__(self, include_cookie: bool = True) -> None:
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "OPTIONS", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=30, pool_maxsize=30)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive",
            }
        )
        cookie = os.environ.get("EASTMONEY_COOKIE", "").strip()
        if include_cookie and cookie:
            self.session.headers["Cookie"] = cookie
        if not include_cookie:
            self.session.headers["Connection"] = "close"

    def proxies(self) -> dict[str, str] | None:
        proxy = os.environ.get("EASTMONEY_PROXY", "").strip()
        if not proxy:
            return None
        return {"http": proxy, "https": proxy}

    def get(self, url: str, params: dict[str, Any], timeout: int = 20) -> requests.Response:
        response = self.session.get(url, params=params, timeout=timeout, proxies=self.proxies())
        response.raise_for_status()
        return response


def fetch_pages(
    url: str,
    params: dict[str, Any],
    page_size: int = 50,
    callback_jsonp: bool = False,
    include_cookie: bool = True,
) -> list[dict[str, Any]]:
    urls = eastmoney_endpoint_candidates(url)
    request_page_size = min(page_size, 100)
    page_current = 1
    payload = fetch_page_payload(urls, params, page_current, request_page_size, callback_jsonp, include_cookie)
    data = (payload.get("data") or {}).get("diff") or []
    total = int((payload.get("data") or {}).get("total") or len(data))
    page_count = math.ceil(total / request_page_size)

    while page_current < page_count:
        time.sleep(random.uniform(0.6, 1.2))
        page_current += 1
        payload = fetch_page_payload(urls, params, page_current, request_page_size, callback_jsonp, include_cookie)
        data.extend((payload.get("data") or {}).get("diff") or [])
    return data


def fetch_page_payload(
    urls: list[str],
    params: dict[str, Any],
    page: int,
    page_size: int,
    callback_jsonp: bool,
    include_cookie: bool,
) -> dict[str, Any]:
    last_error: Exception | None = None
    page_params = {**params, "pn": page, "pz": page_size}
    for attempt in range(3):
        for candidate_url in urls:
            try:
                client = EastmoneySession(include_cookie=include_cookie)
                response = client.get(candidate_url, params=page_params)
                return parse_eastmoney_payload(response.text, callback_jsonp=callback_jsonp)
            except requests.exceptions.RequestException as exc:
                last_error = exc
        if attempt < 2:
            time.sleep(random.uniform(1.0, 2.0))
    if last_error is not None:
        raise last_error
    raise RuntimeError("Eastmoney page request failed without an exception")


def eastmoney_endpoint_candidates(url: str) -> list[str]:
    if "push2.eastmoney.com/api/qt/clist/get" not in url:
        return [url]
    candidates = [
        url,
        "http://push2.eastmoney.com/api/qt/clist/get",
        "http://80.push2.eastmoney.com/api/qt/clist/get",
        "http://82.push2.eastmoney.com/api/qt/clist/get",
        "https://push2.eastmoney.com/api/qt/clist/get",
    ]
    unique: list[str] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def parse_eastmoney_payload(text: str, callback_jsonp: bool = False) -> dict[str, Any]:
    if callback_jsonp:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise RuntimeError("Eastmoney JSONP payload did not contain JSON")
        text = text[start : end + 1]
    return json.loads(text)


def fetch_instock_stock_moneyflow(trade_date: date | None = None, indicator: str = "今日") -> list[StockSnapshot]:
    indicator_map = {
        "今日": [
            "f62",
            "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124",
        ],
        "3日": [
            "f267",
            "f12,f14,f2,f127,f267,f268,f269,f270,f271,f272,f273,f274,f275,f276,f257,f258,f124",
        ],
        "5日": [
            "f164",
            "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124",
        ],
        "10日": [
            "f174",
            "f12,f14,f2,f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f260,f261,f124",
        ],
    }
    if indicator not in indicator_map:
        raise ValueError(f"unsupported Eastmoney stock money-flow indicator: {indicator}")

    rows = fetch_pages(
        "http://push2.eastmoney.com/api/qt/clist/get",
        {
            "fid": indicator_map[indicator][0],
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fs": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2",
            "fields": indicator_map[indicator][1],
        },
        page_size=6000,
        include_cookie=False,
    )
    snapshots: list[StockSnapshot] = []
    for row in rows:
        price = to_float(row.get("f2"))
        if price <= 0:
            continue
        symbol = normalize_symbol(row.get("f12"))
        main_net, main_rate, large_net = stock_flow_fields(row, indicator)
        timestamp = eastmoney_row_timestamp(row, trade_date)
        snapshots.append(
            StockSnapshot(
                symbol=symbol,
                name=str(row.get("f14") or symbol),
                timestamp=timestamp,
                price=price,
                pct_change=to_float(row.get("f3") or row.get("f127") or row.get("f109") or row.get("f160")),
                open=0,
                high=0,
                low=0,
                prev_close=0,
                volume=0,
                amount=0,
                turnover_rate=0,
                main_net_inflow=main_net,
                large_order_net_inflow=large_net,
                super_large_order_net_inflow=to_float(row.get("f66")),
                market_cap=0,
            )
        )
    return snapshots


def stock_flow_fields(row: dict[str, Any], indicator: str) -> tuple[float, float, float]:
    if indicator == "今日":
        return to_float(row.get("f62")), to_float(row.get("f184")), to_float(row.get("f72"))
    if indicator == "3日":
        return to_float(row.get("f267")), to_float(row.get("f268")), to_float(row.get("f271"))
    if indicator == "5日":
        return to_float(row.get("f164")), to_float(row.get("f165")), to_float(row.get("f168"))
    return to_float(row.get("f174")), to_float(row.get("f175")), to_float(row.get("f178"))


def fetch_instock_sector_fund_flow(
    trade_date: date | None = None,
    sector_type: SectorType = SectorType.CONCEPT,
    indicator: str = "今日",
) -> list[SectorSnapshot]:
    sector_type_map = {SectorType.INDUSTRY: "2", SectorType.CONCEPT: "3"}
    indicator_map = {
        "今日": [
            "f62",
            "1",
            "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124",
        ],
        "5日": [
            "f164",
            "5",
            "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124",
        ],
        "10日": [
            "f174",
            "10",
            "f12,f14,f2,f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f260,f261,f124",
        ],
    }
    if indicator not in indicator_map:
        raise ValueError(f"unsupported Eastmoney sector money-flow indicator: {indicator}")

    rows = fetch_pages(
        "http://80.push2.eastmoney.com/api/qt/clist/get",
        {
            "po": "1",
            "np": "1",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fltt": "2",
            "invt": "2",
            "fid0": indicator_map[indicator][0],
            "fs": f"m:90 t:{sector_type_map[sector_type]}",
            "stat": indicator_map[indicator][1],
            "fields": indicator_map[indicator][2],
        },
        page_size=500,
        include_cookie=False,
    )
    snapshots: list[SectorSnapshot] = []
    for row in rows:
        name = str(row.get("f14") or "")
        if not name or row.get("f2") == "-":
            continue
        main_net, _main_rate, _large_net = stock_flow_fields(row, indicator)
        leader_code = row.get("f205") or row.get("f258") or row.get("f261")
        top_symbols = [normalize_symbol(leader_code)] if leader_code else []
        timestamp = eastmoney_row_timestamp(row, trade_date)
        snapshots.append(
            SectorSnapshot(
                sector_id=f"instock_em_{sector_type.value}_{name}",
                sector_name=name,
                sector_type=sector_type,
                timestamp=timestamp,
                pct_change=to_float(row.get("f3") or row.get("f109") or row.get("f160")),
                main_net_inflow=main_net,
                amount=0,
                amount_growth=0,
                up_count=0,
                down_count=0,
                limit_up_count=0,
                limit_down_count=0,
                new_high_count=0,
                breadth=0,
                top_symbols=top_symbols,
                continuity_days=0,
                catalyst_strength=0,
                board_open_rate=0,
                tail_support=50,
            )
        )
    return snapshots


def fetch_instock_all_sector_fund_flow(trade_date: date | None = None, indicator: str = "今日") -> list[SectorSnapshot]:
    sectors: list[SectorSnapshot] = []
    sectors.extend(fetch_instock_sector_fund_flow(trade_date, SectorType.INDUSTRY, indicator))
    sectors.extend(fetch_instock_sector_fund_flow(trade_date, SectorType.CONCEPT, indicator))
    return sectors


def eastmoney_row_timestamp(row: dict[str, Any], trade_date: date | None = None) -> datetime:
    now = datetime.now(CN_TZ)
    raw_timestamp = to_float(row.get("f124"))
    if raw_timestamp > 0:
        source_timestamp = datetime.fromtimestamp(raw_timestamp, tz=CN_TZ)
        selected_date = trade_date or now.date()
        if selected_date == now.date() and source_timestamp > now:
            return now
        return source_timestamp
    selected_date = trade_date or now.date()
    if selected_date == now.date():
        return now
    return datetime.combine(selected_date, dt_time(15, 30), tzinfo=CN_TZ)
