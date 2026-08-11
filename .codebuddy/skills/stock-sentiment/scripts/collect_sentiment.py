#!/usr/bin/env python3
"""
stock-sentiment 数据采集脚本
用法：python collect_sentiment.py <股票代码或名称>
输出：JSON 格式的六维分析原始数据，写入 stdout
"""

import sys
import json
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

# ── 工具路径 ──────────────────────────────────────────────
WESTOCK = shutil.which("westock") or "/Users/zikozhang/.local/bin/westock"


def run(args: list[str], timeout: int = 20) -> str:
    """执行 westock 命令，返回 stdout 字符串；失败返回错误描述。"""
    try:
        result = subprocess.run(
            [WESTOCK] + args,
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] westock {' '.join(args)}"
    except Exception as e:
        return f"[ERROR] {e}"


def resolve_code(raw: str) -> str:
    """若输入不带市场前缀，调用 search 取第一个结果的 code。"""
    prefixes = ("sh", "sz", "bj", "hk", "us", "t.", "ks", "kq")
    if any(raw.lower().startswith(p) for p in prefixes):
        return raw
    output = run(["search", raw])
    # 解析 markdown 表格，跳过表头行和分隔行，取第一数据行的第一列
    for line in output.splitlines():
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) >= 2 and cols[0] not in ("code", "---", "----") and not cols[0].startswith("-"):
            return cols[0]
    return raw  # fallback


def is_ashare(code: str) -> bool:
    return code.lower().startswith(("sh", "sz", "bj"))


def parallel_run(tasks: dict[str, list[str]]) -> dict[str, str]:
    """并行执行多个 westock 命令，返回 {key: stdout} 字典。"""
    results = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(run, args): key for key, args in tasks.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            results[key] = fut.result()
    return results


def find_sector_code(hot_sector_output: str, stock_name: str) -> Optional[str]:
    """
    从 hot sector 输出中按股票名汉字关键词匹配板块 symbol（pt0 开头）。
    遍历每行，找到同行有 pt0 开头的 symbol 且板块名中包含股票名汉字的行。
    返回匹配到的板块 symbol，或 None。
    """
    # 提取股票名中的所有汉字
    cn_chars = [c for c in stock_name if "\u4e00" <= c <= "\u9fff"]
    if not cn_chars:
        return None

    lines = hot_sector_output.splitlines()
    for line in lines:
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 3:
            continue

        # 找本行的 symbol（pt0 开头）
        symbol = None
        for col in cols:
            if col.startswith("pt0"):
                symbol = col
                break
        if not symbol:
            continue

        # 检查本行其他列是否包含股票名汉字
        for col in cols:
            if col == symbol:
                continue
            if any(c in col for c in cn_chars):
                return symbol

    return None


def collect(raw_input: str) -> dict:
    """主采集函数，返回结构化数据字典。"""
    code = resolve_code(raw_input.strip())
    ashare = is_ashare(code)

    # ── 第一轮：全部并行 ──────────────────────────────────
    round1_tasks = {
        "quote":        ["quote", code],
        "kline":        ["kline", code, "--period", "day", "--limit", "30"],
        "technical":    ["technical", code],
        "fund_flow":    ["fund", "flow", code],
        "news":         ["news", "list", code, "--limit", "10"],
        "finance":      ["finance", code, "--limit", "1"],
        "hot_stock":    ["hot", "stock"],
        "sse_index":    ["quote", "sh000001"],
        "hot_sector":   ["hot", "sector"],
        "cn_pmi":       ["macro", "indicator", "cn_pmi", "--limit", "3"],
        "cn_lpr":       ["macro", "indicator", "cn_lpr", "--limit", "3"],
        "us_inflation": ["macro", "indicator", "us_inflation", "--limit", "3"],
        "us_monetary":  ["macro", "indicator", "us_monetary", "--limit", "3"],
        "global_index": ["quote", "usIXIC,usDJI,hkHSI,hkHSTECH"],
    }
    round1 = parallel_run(round1_tasks)

    # ── 第二轮：A 股专用（龙虎榜 + 北向）────────────────
    round2: dict[str, str] = {}
    if ashare:
        round2_tasks = {
            "lhb":           ["fund", "lhb", code],
            "north_holding": ["fund", "north-holding", code],
        }
        round2 = parallel_run(round2_tasks)

    # ── 第三轮：行业估值对标 ───────────────────────────────
    round3: dict[str, str] = {}
    sector_code = None
    if ashare:
        # 从 quote 结果里提取股票名，用于板块关键词匹配
        stock_name = ""
        for line in round1.get("quote", "").splitlines():
            cols = [c.strip() for c in line.split("|") if c.strip()]
            # quote 表格：code | name | price | ... 跳过表头和分隔行
            if len(cols) >= 2 and cols[0] == code:
                stock_name = cols[1] if len(cols) > 1 else ""
                break

        sector_code = find_sector_code(round1.get("hot_sector", ""), stock_name)
        if sector_code:
            round3["sector_valuation"] = run(["sector", "valuation", sector_code])
        else:
            round3["sector_valuation"] = "[NO_DATA] 无法从 hot_sector 匹配到所属板块"

    return {
        "meta": {
            "input": raw_input,
            "code": code,
            "is_ashare": ashare,
            "sector_code": sector_code,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "round1": round1,
        "round2": round2,
        "round3": round3,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python collect_sentiment.py <股票代码或名称>", file=sys.stderr)
        sys.exit(1)

    raw = " ".join(sys.argv[1:])
    data = collect(raw)
    print(json.dumps(data, ensure_ascii=False, indent=2))
