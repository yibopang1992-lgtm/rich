#!/usr/bin/env python3
"""Build verified price, estimated-return, consensus, and trader-profile datasets."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path

import akshare as ak
import baostock as bs
import pandas as pd


SKILL_DIR = Path(__file__).resolve().parents[1]
REF_DIR = SKILL_DIR / "references"
ALIASES = {
    "ST禾信": ("688622", "*ST禾信"),
    "兔宝宝": ("002043", "兔 宝 宝"),
    "粤电力A": ("000539", "粤电力Ａ"),
    "艾艾精工": ("603580", "艾艾精工"),
    "金螳螂": ("002081", "金 螳 螂"),
}


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def exchange_symbol(code: str) -> str:
    if code.startswith(("4", "8", "9")):
        return f"bj{code}"
    if code.startswith(("5", "6", "68")):
        return f"sh{code}"
    return f"sz{code}"


def fetch_one(code: str, start: str, end: str) -> tuple[str, list[dict], str]:
    symbol = exchange_symbol(code)
    last_error = ""
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust="")
            rows = []
            for idx, row in df.iterrows():
                dt = idx if isinstance(idx, date) else row.get("date", idx)
                if isinstance(dt, pd.Timestamp):
                    dt = dt.date()
                amount = float(row.get("amount", 0) or 0)
                volume = float(row.get("volume", 0) or 0)
                rows.append(
                    {
                        "code": code,
                        "date": dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": volume,
                        "amount": amount,
                        "turnover": float(row.get("turnover", 0) or 0),
                        "vwap": amount / volume if volume else math.nan,
                        "source": "新浪财经 stock_zh_a_daily（未复权）",
                        "source_url": f"https://finance.sina.com.cn/realstock/company/{symbol}/nc.shtml",
                    }
                )
            if rows:
                return code, rows, ""
            last_error = "empty history"
        except Exception as exc:  # network boundary
            last_error = repr(exc)
        time.sleep(0.35 * (attempt + 1))
    return code, [], last_error


def fetch_industries(as_of: str) -> pd.DataFrame:
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"Baostock login failed: {lg.error_msg}")
    try:
        rs = bs.query_stock_industry(date=datetime.strptime(as_of, "%Y%m%d").strftime("%Y-%m-%d"))
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(dict(zip(rs.fields, rs.get_row_data())))
        if rs.error_code != "0":
            raise RuntimeError(rs.error_msg)
        return pd.DataFrame(rows)
    finally:
        bs.logout()


def make_stock_map(transactions: pd.DataFrame, seats: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    master = ak.stock_info_a_code_name().copy()
    exact = dict(zip(master["name"], master["code"].astype(str).str.zfill(6)))
    stocks = sorted(set(transactions.loc[transactions["quality"] != "source_error", "stock"]) | set(seats["stock"]))
    rows, failures = [], []
    for stock in stocks:
        if stock in exact:
            code, canonical = exact[stock], stock
        elif stock in ALIASES:
            code, canonical = ALIASES[stock]
        else:
            failures.append({"stock": stock, "reason": "股票简称无法与当前A股代码表精确匹配"})
            continue
        rows.append({"stock": stock, "code": code, "canonical_name": canonical})
    return pd.DataFrame(rows), pd.DataFrame(failures)


def add_industry(stock_map: pd.DataFrame, as_of: str) -> pd.DataFrame:
    industries = fetch_industries(as_of)
    if industries.empty:
        stock_map["industry"] = ""
        return stock_map
    industries["code6"] = industries["code"].str.split(".").str[-1]
    ind = industries.sort_values("updateDate").drop_duplicates("code6", keep="last")
    out = stock_map.merge(ind[["code6", "industry", "updateDate"]], left_on="code", right_on="code6", how="left")
    out.drop(columns=["code6"], inplace=True)
    out["industry"] = out["industry"].fillna("未分类")
    return out


def execution_price(code: str, report_date: str, window: str, price_groups: dict[str, pd.DataFrame]) -> float:
    df = price_groups.get(code)
    if df is None or df.empty:
        return math.nan
    eligible = df[df["date"] <= report_date].sort_values("date")
    if eligible.empty:
        return math.nan
    period = eligible.tail(3 if window == "3日" else 1)
    amount, volume = period["amount"].sum(), period["volume"].sum()
    return float(amount / volume) if volume else math.nan


def calculate_returns(transactions: pd.DataFrame, stock_map: pd.DataFrame, prices: pd.DataFrame, end_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    tx = transactions.merge(stock_map[["stock", "code", "industry"]], on="stock", how="left")
    price_groups = {code: grp.copy() for code, grp in prices.groupby("code")}
    tx["exec_price_est"] = tx.apply(
        lambda r: execution_price(str(r.get("code", "")), r["date"], r["window"], price_groups), axis=1
    )
    tx["amount_w_num"] = pd.to_numeric(tx["amount_w"], errors="coerce")
    tx["shares_est"] = tx["amount_w_num"] * 10000 / tx["exec_price_est"]
    tx["pricing_rule"] = tx["window"].map({"单日": "当日全市场VWAP", "3日": "截至榜单日最近3个交易日全市场VWAP"})
    tx["price_source"] = "新浪未复权日线；金额/成交量计算VWAP"
    tx["return_confidence"] = tx.apply(
        lambda r: "不可计算" if pd.isna(r["shares_est"]) else ("低" if r["window"] == "3日" or r["quality"] != "verified" else "中"),
        axis=1,
    )

    buy_rows = []
    open_lots: dict[tuple[str, str], deque] = defaultdict(deque)
    unmatched_sales = []
    tx = tx.reset_index(drop=True)
    for idx, row in tx.sort_values(["date"]).iterrows():
        key = (row["trader"], row["stock"])
        shares = row["shares_est"]
        if row["side"] == "买入":
            lot = {
                "tx_index": int(idx),
                "buy_date": row["date"],
                "trader": row["trader"],
                "stock": row["stock"],
                "code": row.get("code", ""),
                "industry": row.get("industry", ""),
                "amount_w": row["amount_w_num"],
                "buy_price_est": row["exec_price_est"],
                "shares_est": shares,
                "remaining": shares,
                "realized_shares": 0.0,
                "realized_proceeds": 0.0,
                "first_sell_date": "",
                "last_sell_date": "",
                "window": row["window"],
                "source_quality": row["quality"],
                "return_confidence": row["return_confidence"],
                "source_image": row["source_image"],
                "note": row["note"],
            }
            buy_rows.append(lot)
            if pd.notna(shares) and shares > 0:
                open_lots[key].append(lot)
        elif row["side"] == "卖出" and pd.notna(shares) and shares > 0:
            sell_left = float(shares)
            while sell_left > 1e-8 and open_lots[key]:
                lot = open_lots[key][0]
                used = min(sell_left, lot["remaining"])
                lot["remaining"] -= used
                lot["realized_shares"] += used
                lot["realized_proceeds"] += used * row["exec_price_est"]
                lot["first_sell_date"] = lot["first_sell_date"] or row["date"]
                lot["last_sell_date"] = row["date"]
                sell_left -= used
                if lot["remaining"] <= 1e-8:
                    open_lots[key].popleft()
            if sell_left > 1e-6:
                unmatched_sales.append({
                    "date": row["date"], "trader": row["trader"], "stock": row["stock"],
                    "code": row.get("code", ""), "unmatched_shares_est": sell_left,
                    "reason": "样本窗口内未见足额先前买入，无法准确反推成本与收益",
                })

    end_close = prices[prices["date"] <= end_date].sort_values("date").drop_duplicates("code", keep="last").set_index("code")["close"].to_dict()
    for lot in buy_rows:
        cost = lot["shares_est"] * lot["buy_price_est"] if pd.notna(lot["shares_est"]) else math.nan
        realized_exit = lot["realized_proceeds"] / lot["realized_shares"] if lot["realized_shares"] else math.nan
        realized_cost = lot["realized_shares"] * lot["buy_price_est"]
        lot["realized_exit_price_est"] = realized_exit
        lot["realized_return_pct"] = lot["realized_proceeds"] / realized_cost - 1 if realized_cost else math.nan
        lot["open_shares_est"] = lot["remaining"] if pd.notna(lot["remaining"]) else math.nan
        close = end_close.get(str(lot["code"]), math.nan)
        lot["end_close"] = close
        lot["unrealized_return_pct"] = close / lot["buy_price_est"] - 1 if pd.notna(close) and lot["buy_price_est"] else math.nan
        terminal_value = lot["realized_proceeds"] + (lot["remaining"] * close if pd.notna(close) and pd.notna(lot["remaining"]) else 0)
        lot["blended_return_pct"] = terminal_value / cost - 1 if cost else math.nan
        lot["holding_calendar_days_to_first_sell"] = (
            (datetime.fromisoformat(lot["first_sell_date"]) - datetime.fromisoformat(lot["buy_date"])).days
            if lot["first_sell_date"] else math.nan
        )
        lot["status"] = "不可计算" if pd.isna(cost) or pd.isna(close) else ("已全部卖出" if lot["remaining"] <= 1e-8 else ("部分卖出" if lot["realized_shares"] else "持有至截止日"))
        if lot["window"] == "3日":
            lot["note"] = (lot["note"] + "；" if lot["note"] else "") + "3日榜单无法定位逐笔成交日，收益为区间VWAP估算"
    return pd.DataFrame(buy_rows), pd.DataFrame(unmatched_sales)


def make_profiles(investments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    usable = investments[pd.notna(investments["amount_w"])].copy()
    for trader, grp in usable.groupby("trader"):
        exited = grp[pd.notna(grp["holding_calendar_days_to_first_sell"])]
        quick = exited["holding_calendar_days_to_first_sell"].le(1).mean() if len(exited) else math.nan
        sectors = grp.groupby("industry")["amount_w"].sum().sort_values(ascending=False)
        top_sectors = "；".join(f"{k}({v:.0f}万)" for k, v in sectors.head(3).items())
        rets = pd.to_numeric(grp["blended_return_pct"], errors="coerce").dropna()
        median_hold = exited["holding_calendar_days_to_first_sell"].median() if len(exited) else math.nan
        if len(grp) < 3:
            style = "样本不足，只记录观察项"
        elif pd.notna(quick) and quick >= 0.5:
            style = "快进快出/事件驱动，次日兑现风险较高"
        elif pd.notna(median_hold) and median_hold <= 3:
            style = "短波段，偏好1–3日内轮动兑现"
        else:
            style = "样本内持有更分散，需结合新单确认是否为铺垫或波段"
        rows.append({
            "trader": trader,
            "buy_count": len(grp),
            "distinct_stocks": grp["stock"].nunique(),
            "total_buy_amount_w": grp["amount_w"].sum(),
            "exited_sample_count": len(exited),
            "quick_exit_rate_1d": quick,
            "median_calendar_days_to_first_sell": median_hold,
            "win_rate_est": (rets > 0).mean() if len(rets) else math.nan,
            "median_blended_return_pct": rets.median() if len(rets) else math.nan,
            "top_industries": top_sectors,
            "style_label": style,
            "confidence": "高" if len(grp) >= 15 else ("中" if len(grp) >= 6 else "低"),
            "risk_rule": "新图出现该席位后，先查其历史1日兑现率与同股后续卖出；不得把龙头席位等同于买入建议",
        })
    return pd.DataFrame(rows).sort_values(["buy_count", "total_buy_amount_w"], ascending=False)


def make_consensus(transactions: pd.DataFrame, stock_map: pd.DataFrame) -> pd.DataFrame:
    tx = transactions[(transactions["side"] == "买入") & (transactions["quality"] != "source_error")].merge(
        stock_map[["stock", "code", "industry"]], on="stock", how="left"
    )
    tx["amount_w_num"] = pd.to_numeric(tx["amount_w"], errors="coerce")
    out = tx.groupby(["date", "stock", "code", "industry"], dropna=False).agg(
        distinct_buyers=("trader", "nunique"),
        buyers=("trader", lambda s: "、".join(sorted(set(s)))),
        disclosed_buy_amount_w=("amount_w_num", lambda s: s.sum(min_count=1)),
    ).reset_index()
    out["consensus_level"] = out["distinct_buyers"].map(lambda n: "多游资强共识" if n >= 4 else ("多游资共识" if n >= 2 else "单席位"))
    return out.sort_values(["date", "distinct_buyers", "disclosed_buy_amount_w"], ascending=[True, False, False])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="20260720")
    parser.add_argument("--end", default="20260815")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    tx = read_tsv(REF_DIR / "transactions.tsv")
    seats = read_tsv(REF_DIR / "eastmoney_seats.tsv")
    stock_map, mapping_failures = make_stock_map(tx, seats)
    stock_map = add_industry(stock_map, args.end)

    # Reuse a same-window cache when present. This also makes iterative OCR fixes cheap.
    raw_columns = ["code", "date", "open", "high", "low", "close", "volume", "amount", "turnover", "vwap", "source", "source_url"]
    cached_path = output / "prices.csv"
    cached = pd.DataFrame(columns=raw_columns)
    if cached_path.exists():
        prior = pd.read_csv(cached_path, dtype={"code": str})
        if set(raw_columns).issubset(prior.columns):
            prior["date"] = prior["date"].astype(str)
            cached = prior.loc[
                (prior["date"] >= datetime.strptime(args.start, "%Y%m%d").strftime("%Y-%m-%d"))
                & (prior["date"] <= datetime.strptime(args.end, "%Y%m%d").strftime("%Y-%m-%d")), raw_columns
            ].copy()
    all_prices, fetch_failures = cached.to_dict("records"), []
    cached_codes = set(cached["code"].astype(str).str.zfill(6))
    # AKShare's Sina decoder embeds V8 through mini-racer and is not thread-safe.
    # Keep network fetches serial: correctness and reproducibility beat latency.
    for code in stock_map["code"]:
        if str(code).zfill(6) in cached_codes:
            continue
        code, rows, error = fetch_one(code, args.start, args.end)
        all_prices.extend(rows)
        if error:
            fetch_failures.append({"code": code, "reason": error})
    prices = pd.DataFrame(all_prices)
    if not prices.empty:
        prices = prices.merge(stock_map[["code", "stock", "canonical_name", "industry"]], on="code", how="left")
        prices.sort_values(["stock", "date"], inplace=True)

    investments, unmatched_sales = calculate_returns(tx, stock_map, prices, datetime.strptime(args.end, "%Y%m%d").strftime("%Y-%m-%d"))
    profiles = make_profiles(investments)
    consensus = make_consensus(tx, stock_map)

    datasets = {
        "stock_map.csv": stock_map,
        "prices.csv": prices,
        "transactions_enriched.csv": tx.merge(stock_map[["stock", "code", "industry"]], on="stock", how="left"),
        "investments.csv": investments,
        "trader_profiles.csv": profiles,
        "consensus.csv": consensus,
        "unmatched_sales.csv": unmatched_sales,
        "mapping_failures.csv": mapping_failures,
        "price_fetch_failures.csv": pd.DataFrame(fetch_failures),
        "eastmoney_seats.csv": seats,
    }
    for name, df in datasets.items():
        df.to_csv(output / name, index=False, encoding="utf-8-sig")
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "price_start": args.start,
        "price_end": args.end,
        "price_source": "新浪财经未复权日线；Baostock抽样交叉核对",
        "transaction_rows": len(tx),
        "unique_stock_labels": int(len(set(tx["stock"]) | set(seats["stock"]))),
        "mapped_stocks": len(stock_map),
        "price_rows": len(prices),
        "investment_rows": len(investments),
        "mapping_failures": len(mapping_failures),
        "price_fetch_failures": len(fetch_failures),
        "method": "单日榜单用当日市场VWAP；3日榜单用最近3个交易日市场VWAP；同一游资同股按FIFO匹配卖出；未卖出按截止日收盘价估值。",
        "limitations": "龙虎榜披露的是席位汇总金额而非逐笔成交价，本报告收益均为估算；截图遮挡和3日榜单降低置信度。",
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
