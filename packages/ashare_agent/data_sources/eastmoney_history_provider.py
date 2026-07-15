from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from time import sleep
from typing import Any
from typing import Callable
from zoneinfo import ZoneInfo

import requests

from ashare_agent.data_sources.akshare_provider import (
    is_limit_up,
    normalize_symbol,
    to_float,
)
from ashare_agent.data_sources.baostock_provider import load_stock_codes
from ashare_agent.models import StockSnapshot


CN_TZ = ZoneInfo("Asia/Shanghai")


def eastmoney_secid(code: str) -> str:
    raw = code.strip().zfill(6)
    market_id = "1" if raw.startswith(("6", "9")) else "0"
    return f"{market_id}.{raw}"


def fetch_eastmoney_daily_snapshots_range(
    start_date: date,
    end_date: date,
    max_symbols: int | None = None,
    workers: int = 24,
    progress: Callable[[int, int], None] | None = None,
    stock_rows: list[dict[str, Any]] | None = None,
) -> list[StockSnapshot]:
    stock_rows = stock_rows or load_stock_universe(end_date)
    if max_symbols is not None and max_symbols > 0:
        stock_rows = stock_rows[:max_symbols]

    total = len(stock_rows)
    snapshots: list[StockSnapshot] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(fetch_one_stock_history, row, start_date, end_date)
            for row in stock_rows
        ]
        for index, future in enumerate(as_completed(futures), start=1):
            try:
                snapshots.extend(future.result())
            except Exception:
                pass
            if progress and (index == total or index % 500 == 0):
                progress(index, total)
    return snapshots


def fetch_one_stock_history(row: dict, start_date: date, end_date: date) -> list[StockSnapshot]:
    code = str(row.get("代码") or "").strip().zfill(6)
    name = str(row.get("名称") or code).strip()
    if not code:
        return []

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": eastmoney_secid(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
    }
    response = requests.get(url, params=params, headers=headers, timeout=12)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    symbol = normalize_symbol(code)
    market_cap = to_float(row.get("总市值"))
    snapshots: list[StockSnapshot] = []

    for item in klines:
        parts = str(item).split(",")
        if len(parts) < 11:
            continue
        trade_date = date.fromisoformat(parts[0])
        open_price = to_float(parts[1])
        close_price = to_float(parts[2])
        high = to_float(parts[3])
        low = to_float(parts[4])
        volume = to_float(parts[5])
        amount = to_float(parts[6])
        pct_change = to_float(parts[8])
        change_amount = to_float(parts[9])
        turnover = to_float(parts[10])
        prev_close = close_price - change_amount if close_price >= change_amount else 0
        snapshots.append(
            StockSnapshot(
                symbol=symbol,
                name=name,
                timestamp=datetime.combine(trade_date, time(15, 0), tzinfo=CN_TZ),
                price=close_price,
                pct_change=pct_change,
                open=open_price,
                high=high,
                low=low,
                prev_close=prev_close,
                volume=volume,
                amount=amount,
                turnover_rate=turnover,
                main_net_inflow=0,
                large_order_net_inflow=0,
                super_large_order_net_inflow=0,
                limit_up=is_limit_up(symbol, pct_change),
                limit_down=pct_change <= -9.5,
                recent_5d_gain=0,
                market_cap=market_cap,
            )
        )
    return snapshots


def load_stock_universe(trade_date: date, retries: int = 3) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            rows = fetch_eastmoney_stock_rows_paged()
            if rows:
                return rows
        except Exception as exc:
            last_error = exc
            sleep(0.5 * (attempt + 1))

    try:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            raise RuntimeError(login.error_msg)
        try:
            codes = load_stock_codes(bs, trade_date)
            return [
                {
                    "代码": code.split(".")[1],
                    "名称": name,
                    "总市值": 0,
                }
                for code, name in codes
            ]
        finally:
            bs.logout()
    except Exception as exc:
        last_error = exc

    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        rows = df.to_dict("records")
        return [
            {
                "代码": row.get("代码"),
                "名称": row.get("名称"),
                "总市值": row.get("总市值", 0),
            }
            for row in rows
        ]
    except Exception:
        if last_error:
            raise last_error
        raise


def fetch_eastmoney_stock_rows_paged(page_size: int = 1000) -> list[dict[str, Any]]:
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
    }
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {
            "pn": page,
            "pz": page_size,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f12,f14,f20",
        }
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json().get("data") or {}
        diff = data.get("diff") or []
        if not diff:
            break
        rows.extend(
            {
                "代码": item.get("f12"),
                "名称": item.get("f14"),
                "总市值": item.get("f20", 0),
            }
            for item in diff
        )
        if len(diff) < page_size:
            break
        page += 1
    return rows


def fetch_eastmoney_daily_snapshots(
    trade_date: date,
    max_symbols: int | None = None,
    workers: int = 24,
) -> list[StockSnapshot]:
    return fetch_eastmoney_daily_snapshots_range(
        trade_date,
        trade_date,
        max_symbols=max_symbols,
        workers=workers,
    )
