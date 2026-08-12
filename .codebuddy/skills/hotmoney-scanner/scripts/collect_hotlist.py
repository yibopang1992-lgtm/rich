#!/usr/bin/env python3
"""
hotmoney-scanner 数据采集脚本
用法：python collect_hotlist.py [--date YYYY-MM-DD]
输出：JSON 格式的全市场游资选股所需数据，写入 stdout

数据来源：全部通过 westock CLI 获取，无任何外部依赖。

修复记录：
  - 修复 #1：westock lhb 不支持 --date，历史复盘时跳过龙虎榜并标注
  - 修复 #2：新增二阶段个股行情采集（quote + kline 批量查询）
  - 修复 #4：新增板块历史 K 线采集，支持判断连续上涨天数
  - 修复 #5：宏观改为 cn_calendar_future（未来事件日历），对日内操作更实用
  - 修复 #6：新增前置交易日判断，非交易日直接返回提示
  - 修复 #7：westock 路径改为 os.path.expanduser 通用 fallback
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from typing import Optional, List

# ── 工具路径（修复 #7：通用 fallback，不硬编码个人路径）──────
WESTOCK = shutil.which("westock") or os.path.expanduser("~/.local/bin/westock")

# 二阶段个股采集：单支超时略长，批量并行
LHB_STOCK_TIMEOUT = 30
KLINE_TIMEOUT = 20


def run(args: List[str], timeout: int = 25) -> str:
    """执行 westock 命令，返回 stdout 字符串；超时或失败返回错误描述。"""
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


def parallel_run(tasks: dict, timeout: int = 25) -> dict:
    """并行执行多个 westock 命令，返回 {key: stdout} 字典。"""
    results = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(run, args, timeout): key for key, args in tasks.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            results[key] = fut.result()
    return results


def check_trading_day(trade_date: str) -> bool:
    """
    修复 #6：调用 westock trade-calendar 判断是否交易日。
    返回 True=交易日，False=非交易日或查询失败。
    """
    output = run(["trade-calendar", "--date", trade_date], timeout=10)
    if "[ERROR]" in output or "[TIMEOUT]" in output:
        # 查询失败时保守放行，让后续命令自然报错
        return True
    # westock trade-calendar 返回表格，trading 列为 true/false
    for line in output.splitlines():
        cols = [c.strip() for c in line.split("|") if c.strip()]
        # 跳过表头和分隔行
        if len(cols) >= 2 and cols[0] not in ("日期", "date", "---", "----") and not cols[0].startswith("-"):
            # 第二列是交易日字段，westock 返回中文"是"/"否"
            return cols[1] in ("是", "true", "True", "1", "yes")
    return True  # 解析不到时保守放行


def parse_lhb_codes(lhb_output: str) -> List[str]:
    """
    从 westock lhb 的 Markdown 表格输出中提取股票代码列表。
    返回带市场前缀的代码列表，如 ['sh600519', 'sz000001']。
    去重、过滤无效行。
    """
    codes = []
    seen = set()
    for line in lhb_output.splitlines():
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 2:
            continue
        code = cols[0]
        # 跳过表头和分隔行
        if code in ("code", "---", "----") or code.startswith("-"):
            continue
        # 有效 A 股代码以 sh/sz/bj 开头
        if code.lower().startswith(("sh", "sz", "bj")) and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def parse_sector_codes(sector_ranking_output: str) -> List[str]:
    """
    从 westock sector ranking 的输出中提取板块代码（pt 开头）。
    用于后续查询板块历史 K 线判断连续上涨。
    最多取 Top 6（行业涨幅前3 + 概念涨幅前3）。
    """
    codes = []
    seen = set()
    for line in sector_ranking_output.splitlines():
        cols = [c.strip() for c in line.split("|") if c.strip()]
        for col in cols:
            if col.startswith("pt") and col not in seen:
                seen.add(col)
                codes.append(col)
                if len(codes) >= 6:
                    return codes
    return codes


def collect(trade_date: Optional[str] = None) -> dict:
    """
    主采集函数，返回游资选股所需的全市场数据。
    trade_date: YYYY-MM-DD，不传则为当日。
    """
    today = trade_date or date.today().strftime("%Y-%m-%d")
    is_history_mode = trade_date is not None  # 是否为历史复盘模式

    # ── 修复 #6：前置交易日判断 ──────────────────────────────
    is_trading = check_trading_day(today)
    if not is_trading:
        return {
            "meta": {
                "trade_date": today,
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "westock_path": WESTOCK,
                "is_trading_day": False,
            },
            "error": f"{today} 非交易日，无数据可采集。请指定交易日或不传日期（默认当日）。",
        }

    # ── 第一阶段：全市场维度数据（全部并行）──────────────────
    # 修复 #1：westock lhb 不支持 --date，历史模式跳过龙虎榜
    # 修复 #5：宏观改为 cn_calendar_future，查当日起未来重要事件
    round1_tasks = {
        # 板块行情榜（行业涨幅 + 概念涨幅 + 资金流入 + 北向热门）
        "sector_ranking":  ["sector", "ranking"],

        # 热搜（股票 + 板块）
        "hot_stock":       ["hot", "stock"],
        "hot_sector":      ["hot", "sector"],

        # 全市场涨跌分布（11档区间 + 上涨占比 + 两市成交额）
        # 修复 #3：明确用 changedist 取上涨占比/区间分布
        "changedist":      ["changedist"],

        # 大盘总览（市场画像总评：14维度得分）
        "market_summary":  ["market-overview"],

        # 涨跌停家数 + 多周期上涨家数趋势
        # 修复 #3：明确用 updown 取涨停/跌停家数
        "market_updown":   ["market-overview", "--type", "updown"],

        # 主要指数行情
        "quote_sh":        ["quote", "sh000001"],   # 上证
        "quote_cyb":       ["quote", "sz399006"],   # 创业板
        "quote_sz":        ["quote", "sz399001"],   # 深成指

        # 修复 #5：宏观改为未来事件日历，关注今日起重要政策/数据发布
        "macro_calendar":  ["macro", "indicator", "cn_calendar_future", "--date", today],
    }

    # 修复 #1：历史复盘模式不采集龙虎榜（westock lhb 不支持 --date）
    if not is_history_mode:
        round1_tasks["lhb_hotmoney"]   = ["lhb", "--type", "hotmoney"]
        round1_tasks["lhb_institution"] = ["lhb", "--type", "institution"]
        round1_tasks["lhb_activeseat"] = ["lhb", "--type", "activeseat"]

    round1 = parallel_run(round1_tasks)

    # ── 第二阶段：从龙虎榜提取个股，批量查行情+K线（修复 #2）──
    stock_quotes: dict = {}
    stock_klines: dict = {}
    lhb_codes: List[str] = []

    if not is_history_mode:
        # 合并三张龙虎榜中的股票代码
        all_lhb_output = (
            round1.get("lhb_hotmoney", "") + "\n" +
            round1.get("lhb_institution", "") + "\n" +
            round1.get("lhb_activeseat", "")
        )
        lhb_codes = parse_lhb_codes(all_lhb_output)

        if lhb_codes:
            codes_str = ",".join(lhb_codes)  # 批量查询，一次调用
            round2_tasks = {
                # 批量实时行情：涨跌幅、是否涨停（price vs price_ceiling）、
                # 换手率、52周高低、近5/10/20日涨幅
                "stock_quotes": ["quote", codes_str],
                # 批量日K（6根）：判断是否涨停、近5日涨幅
                # 注意：westock kline 批量时每只分表输出，AI 分表读取
            }
            # kline 批量每只单独键，避免输出过长难以解析
            for code in lhb_codes[:20]:  # 最多取 20 只，防止超时
                round2_tasks[f"kline_{code}"] = [
                    "kline", code, "--period", "day", "--limit", "6"
                ]

            round2 = parallel_run(round2_tasks, timeout=KLINE_TIMEOUT)
            stock_quotes = {"batch": round2.pop("stock_quotes", "")}
            stock_klines = {k: v for k, v in round2.items() if k.startswith("kline_")}

    # ── 第三阶段：Top 板块历史 K 线（修复 #4：判断连续上涨天数）──
    sector_klines: dict = {}
    sector_codes = parse_sector_codes(round1.get("sector_ranking", ""))
    if sector_codes:
        round3_tasks = {
            f"sector_kline_{code}": ["kline", code, "--period", "day", "--limit", "5"]
            for code in sector_codes
        }
        sector_klines = parallel_run(round3_tasks, timeout=KLINE_TIMEOUT)

    return {
        "meta": {
            "trade_date": today,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "westock_path": WESTOCK,
            "is_trading_day": True,
            "is_history_mode": is_history_mode,
            "lhb_available": not is_history_mode,
            "lhb_codes_count": len(lhb_codes),
            # 历史模式提示
            "note": (
                "历史复盘模式：westock lhb 不支持 --date，龙虎榜数据不可用，"
                "第三步（标的评分）将跳过，仅输出市场情绪和主线板块分析。"
                if is_history_mode else None
            ),
        },
        "market": {
            # changedist：11档涨跌幅区间分布 + 上涨占比（修复 #3：字段来源明确）
            "changedist":   round1.get("changedist", ""),
            # market_updown：涨停/跌停/新高/新低家数（修复 #3：字段来源明确）
            "updown":       round1.get("market_updown", ""),
            # market_summary：14维度画像总评
            "summary":      round1.get("market_summary", ""),
            "quote_sh":     round1.get("quote_sh", ""),
            "quote_sz":     round1.get("quote_sz", ""),
            "quote_cyb":    round1.get("quote_cyb", ""),
        },
        "sector": {
            "ranking":      round1.get("sector_ranking", ""),
            "hot_sector":   round1.get("hot_sector", ""),
            # 板块历史 K 线（修复 #4）：键名 sector_kline_{pt代码}
            "klines":       sector_klines,
        },
        "lhb": {
            # 修复 #1：历史模式下三个字段均为空字符串并附说明
            "hotmoney":     round1.get("lhb_hotmoney", ""),
            "institution":  round1.get("lhb_institution", ""),
            "activeseat":   round1.get("lhb_activeseat", ""),
            "codes":        lhb_codes,  # 解析出的代码列表，供 AI 直接使用
        },
        "stocks": {
            # 修复 #2：个股批量行情 + K 线
            # stock_quotes["batch"]：所有龙虎榜标的的 quote 批量输出
            # stock_klines[kline_{code}]：每只股票 6 根日 K
            "quotes":       stock_quotes,
            "klines":       stock_klines,
        },
        "hot": {
            "stock":        round1.get("hot_stock", ""),
        },
        "macro": {
            # 修复 #5：宏观日历（今日起重要事件），对日内操作更实用
            "calendar_future": round1.get("macro_calendar", ""),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="hotmoney-scanner 数据采集脚本，基于 westock CLI"
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        default=None,
        help=(
            "指定交易日期（默认当日）。"
            "注意：历史复盘模式下龙虎榜不可用，标的评分步骤将跳过。"
        ),
    )
    args = parser.parse_args()

    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(
                "[ERROR] 日期格式不合法，请使用 YYYY-MM-DD，如 2026-08-12",
                file=sys.stderr,
            )
            sys.exit(1)

    data = collect(args.date)
    print(json.dumps(data, ensure_ascii=False, indent=2))
