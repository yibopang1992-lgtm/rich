#!/usr/bin/env python3
"""
retail-stock-picker 数据采集脚本
用法：python collect_market.py [--date YYYY-MM-DD] [--capital 10000]
输出：JSON 格式，写入 stdout

采集逻辑（三阶段）：
  第一阶段：全市场情绪 + 板块榜单（全并行）
  第二阶段：主线板块 Top 成份股行情 + 技术指标（根据第一阶段结果动态查询）
  第三阶段：候选个股日 K（用于判断趋势位置）
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from typing import Optional, List, Dict

# ── 工具路径 ──────────────────────────────────────────────
WESTOCK = shutil.which("westock") or os.path.expanduser("~/.local/bin/westock")

# 第二阶段每个板块最多取多少成份股（修复 #3：取足够多，后续用市值过滤）
TOP_CONSTITUENTS = 80
# 最终候选最多分析几只
MAX_CANDIDATES = 10
# 适合散户的市值区间（亿元）：太小流动性差，太大散户资金影响力低
MARKET_CAP_MIN_YI = 30    # 30亿
MARKET_CAP_MAX_YI = 500   # 500亿（适当放宽，300亿内最优但不硬截）


def run(args: List[str], timeout: int = 25) -> str:
    """执行 westock 命令，返回 stdout；超时或失败返回错误描述。"""
    try:
        result = subprocess.run(
            [WESTOCK] + args,
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] westock {' '.join(args)}"
    except FileNotFoundError:
        return "[ERROR] westock 未安装，请先执行: bash ~/.codebuddy/skills/westock-data/scripts/setup.sh"
    except Exception as e:
        return f"[ERROR] {e}"


def parallel_run(tasks: Dict[str, List[str]], timeout: int = 25) -> Dict[str, str]:
    """并行执行多个 westock 命令，返回 {key: stdout} 字典。"""
    results: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(run, args, timeout): key for key, args in tasks.items()}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()
    return results


def check_trading_day(trade_date: str) -> bool:
    """判断是否交易日，westock 返回中文"是"/"否"。"""
    output = run(["trade-calendar", "--date", trade_date], timeout=10)
    if "[ERROR]" in output or "[TIMEOUT]" in output:
        return True  # 查询失败时保守放行
    for line in output.splitlines():
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) >= 2 and cols[0] not in ("日期", "date", "---", "----") and not cols[0].startswith("-"):
            return cols[1] in ("是", "true", "True", "1", "yes")
    return True


def parse_sector_codes(sector_ranking_output: str) -> List[str]:
    """
    从 sector ranking 输出中提取板块代码（pt 开头）。
    优先取行业涨幅 Top3 + 概念涨幅 Top3，最多 6 个。
    """
    codes: List[str] = []
    seen: set = set()
    for line in sector_ranking_output.splitlines():
        cols = [c.strip() for c in line.split("|") if c.strip()]
        for col in cols:
            if col.startswith("pt") and col not in seen:
                seen.add(col)
                codes.append(col)
                if len(codes) >= 6:
                    return codes
    return codes


def parse_constituent_codes(constituent_output: str) -> List[str]:
    """
    从 sector constituent 输出中提取个股代码。
    取前 TOP_CONSTITUENTS 只。
    """
    codes: List[str] = []
    seen: set = set()
    for line in constituent_output.splitlines():
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 2:
            continue
        code = cols[0]
        if code in ("code", "---", "----") or code.startswith("-"):
            continue
        if code.lower().startswith(("sh", "sz", "bj")) and code not in seen:
            seen.add(code)
            codes.append(code)
            if len(codes) >= TOP_CONSTITUENTS:
                break
    return codes


def collect(trade_date: Optional[str] = None, capital: int = 10000) -> dict:
    """
    主采集函数。
    trade_date: YYYY-MM-DD，不传则为当日。
    capital: 本金（元），用于报告中的仓位计算。
    """
    today = trade_date or date.today().strftime("%Y-%m-%d")

    # ── 前置：交易日判断 ──────────────────────────────────
    if not check_trading_day(today):
        return {
            "meta": {
                "trade_date": today,
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "capital": capital,
                "is_trading_day": False,
            },
            "error": f"{today} 非交易日，无数据可采集。",
        }

    # ── 第一阶段：全市场情绪 + 板块榜单（全并行）─────────
    round1_tasks: Dict[str, List[str]] = {
        # 情绪判断
        "changedist":      ["changedist"],
        "market_updown":   ["market-overview", "--type", "updown"],
        "market_summary":  ["market-overview"],
        # 指数行情
        "quote_sh":        ["quote", "sh000001"],
        "quote_sz":        ["quote", "sz399001"],
        "quote_cyb":       ["quote", "sz399006"],
        # 板块榜单（主线识别核心）
        "sector_ranking":  ["sector", "ranking"],
        "hot_sector":      ["hot", "sector"],
        # 宏观事件（次日是否有重大事件）
        "macro_calendar":  ["macro", "indicator", "cn_calendar_future", "--date", today],
    }
    round1 = parallel_run(round1_tasks)

    # ── 第二阶段：主线板块成份股行情 + 技术指标 ─────────
    # 从 sector ranking 解析板块代码
    sector_codes = parse_sector_codes(round1.get("sector_ranking", ""))

    constituents_raw: Dict[str, str] = {}
    stock_codes_by_sector: Dict[str, List[str]] = {}

    if sector_codes:
        # 先并行拉所有主线板块的成份股列表
        constituent_tasks = {
            f"constituent_{code}": ["sector", "constituent", code]
            for code in sector_codes
        }
        constituent_results = parallel_run(constituent_tasks, timeout=20)
        constituents_raw = constituent_results

        # 解析各板块成份股代码
        for code in sector_codes:
            key = f"constituent_{code}"
            raw = constituent_results.get(key, "")
            stock_codes_by_sector[code] = parse_constituent_codes(raw)

        # 汇总所有成份股，去重，批量查 quote + technical
        all_stock_codes: List[str] = []
        seen_codes: set = set()
        for codes in stock_codes_by_sector.values():
            for c in codes:
                if c not in seen_codes:
                    seen_codes.add(c)
                    all_stock_codes.append(c)
        all_stock_codes = all_stock_codes[:MAX_CANDIDATES * 2]  # 最多查40只

        stock_quotes: str = ""
        stock_technicals: Dict[str, str] = {}

        if all_stock_codes:
            codes_str = ",".join(all_stock_codes)
            round2_tasks: Dict[str, List[str]] = {
                "stock_quotes": ["quote", codes_str],
            }
            # technical 不支持超长批量，按板块分组查
            for sector_code in sector_codes:
                sc = stock_codes_by_sector.get(sector_code, [])
                if sc:
                    round2_tasks[f"technical_{sector_code}"] = [
                        "technical", ",".join(sc[:10])  # 每板块最多10只
                    ]
            round2 = parallel_run(round2_tasks, timeout=30)
            stock_quotes = round2.pop("stock_quotes", "")
            stock_technicals = {k: v for k, v in round2.items() if k.startswith("technical_")}

    # ── 第三阶段：候选股日 K（判断趋势和位置）────────────
    # 修复 #1：取各板块前10（后续AI从 quotes 按 changePercent 重新排序）
    # 修复 #7：--limit 改为 22（20日均线需要至少20根K线）
    candidate_codes: List[str] = []
    for codes in stock_codes_by_sector.values():
        candidate_codes.extend(codes[:10])
    candidate_codes = list(dict.fromkeys(candidate_codes))[:MAX_CANDIDATES * 2]  # 去重取前20

    kline_tasks: Dict[str, List[str]] = {}
    for code in candidate_codes:
        kline_tasks[f"kline_{code}"] = [
            "kline", code, "--period", "day", "--limit", "22"  # 修复 #7
        ]
    stock_klines = parallel_run(kline_tasks, timeout=25) if kline_tasks else {}

    return {
        "meta": {
            "trade_date": today,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "capital": capital,
            "max_position": int(capital * 0.7),   # 最多可用仓位
            "cash_buffer": int(capital * 0.3),     # 现金缓冲
            "is_trading_day": True,
            "westock_path": WESTOCK,
            "sector_codes_found": sector_codes,
            # 修复 #3：市值过滤区间，AI 分析时须过滤掉区间外标的
            "market_cap_filter": {
                "min_yi": MARKET_CAP_MIN_YI,
                "max_yi": MARKET_CAP_MAX_YI,
                "note": "总市值在此区间内的标的才适合散户操作，区间外需降级或排除",
            },
        },
        "market": {
            # 情绪判断（铁律第一条）
            "changedist":    round1.get("changedist", ""),    # 上涨占比 → 此字段
            "updown":        round1.get("market_updown", ""), # 涨/跌停家数 → 此字段
            "summary":       round1.get("market_summary", ""),
            "quote_sh":      round1.get("quote_sh", ""),
            "quote_sz":      round1.get("quote_sz", ""),
            "quote_cyb":     round1.get("quote_cyb", ""),
        },
        "sector": {
            "ranking":       round1.get("sector_ranking", ""),
            "hot_sector":    round1.get("hot_sector", ""),
            # 各板块成份股原始数据（sector_code → 成份股表格）
            "constituents":  constituents_raw,
            # 解析出的成份股代码（sector_code → [code, ...]）
            "stock_codes_by_sector": stock_codes_by_sector,
        },
        "stocks": {
            # 批量行情：涨跌幅、量比、换手率、52周高低、近5/10/20日涨幅
            "quotes":        stock_quotes,
            # 技术指标：MACD/KDJ/RSI/BOLL/均线（按板块分组）
            "technicals":    stock_technicals,
            # 日K线：判断趋势、位置（10根）
            "klines":        stock_klines,
        },
        "macro": {
            # 次日重要宏观事件
            "calendar_future": round1.get("macro_calendar", ""),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="retail-stock-picker 数据采集，基于 westock CLI"
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        default=None,
        help="指定交易日期（默认当日）",
    )
    parser.add_argument(
        "--capital",
        type=int,
        default=10000,
        help="本金金额（元），默认10000",
    )
    args = parser.parse_args()

    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("[ERROR] 日期格式不合法，请使用 YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)

    if args.capital <= 0:
        print("[ERROR] 本金必须大于0", file=sys.stderr)
        sys.exit(1)

    data = collect(args.date, args.capital)
    print(json.dumps(data, ensure_ascii=False, indent=2))
