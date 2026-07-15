from __future__ import annotations

import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ashare_agent.data_sources.baostock_provider import fetch_baostock_daily_snapshots
from ashare_agent.data_sources.akshare_provider import (
    fetch_dragon_tiger_events,
    fetch_limit_up_events,
    fetch_sector_memberships,
    fetch_sector_snapshots,
    fetch_stock_snapshots,
)
from ashare_agent.data_sources.sina_provider import (
    fetch_sina_sector_memberships,
    fetch_sina_sector_snapshots,
    fetch_sina_stock_snapshots,
)
from ashare_agent.data_sources.instock_em_provider import (
    fetch_instock_all_sector_fund_flow,
    fetch_instock_stock_moneyflow,
)
from ashare_agent.data_sources.tushare_provider import (
    fetch_tushare_sector_fund_flow,
    fetch_tushare_stock_moneyflow,
)
from ashare_agent.settings import get_db_path
from ashare_agent.storage.sqlite_store import SQLiteMarketStore
from ashare_agent.strategy.features import build_stock_features


CN_TZ = ZoneInfo("Asia/Shanghai")


def sync_market_data(
    db_path: str | None = None,
    membership_limit: int = 8,
    provider: str = "auto",
    trade_date: date | None = None,
    max_symbols: int | None = None,
    symbols: list[str] | None = None,
) -> dict[str, object]:
    as_of = datetime.now(CN_TZ)
    selected_date = trade_date or as_of.date()
    store = SQLiteMarketStore(db_path or get_db_path())
    store.init_db()

    errors: list[str] = []
    stock_rows = 0
    realtime_rows = 0
    sector_rows = 0
    membership_rows = 0
    moneyflow_rows = 0
    limit_up_rows = 0
    news_event_rows = 0
    feature_rows = 0
    rush_event_rows = 0
    sectors = []
    akshare_sectors_loaded = False

    if provider in {"auto", "akshare"}:
        try:
            stocks = fetch_stock_snapshots(as_of)
            stock_rows = store.save_stock_snapshots(stocks, source="akshare_or_eastmoney")
        except Exception as exc:
            errors.append(f"stock snapshots failed: {type(exc).__name__}: {exc}")

    if stock_rows == 0 and provider in {"auto", "baostock"}:
        try:
            stocks = fetch_baostock_daily_snapshots(selected_date, max_symbols=max_symbols)
            stock_rows = store.save_stock_snapshots(stocks, source="baostock")
        except Exception as exc:
            errors.append(f"baostock daily snapshots failed: {type(exc).__name__}: {exc}")

    if provider in {"auto", "sina"}:
        try:
            selected_symbols = symbols or store.load_latest_symbols(limit=max_symbols)
            if not selected_symbols:
                raise RuntimeError("no symbols provided and no local stock snapshots found")
            realtime = fetch_sina_stock_snapshots(selected_symbols)
            realtime_rows = store.save_realtime_quotes(realtime, source="sina")
            if realtime:
                stock_rows = store.save_stock_snapshots(realtime, source="sina")
        except Exception as exc:
            errors.append(f"sina realtime quotes failed: {type(exc).__name__}: {exc}")

    if provider in {"auto", "akshare"}:
        try:
            sectors = fetch_sector_snapshots(as_of)
            sector_rows = store.save_sector_snapshots(sectors, source="akshare_or_eastmoney")
            akshare_sectors_loaded = sector_rows > 0
        except Exception as exc:
            errors.append(f"sector snapshots failed: {type(exc).__name__}: {exc}")

    if sector_rows == 0 and provider in {"auto", "sina-sector"}:
        try:
            sectors = fetch_sina_sector_snapshots(as_of)
            sector_rows = store.save_sector_snapshots(sectors, source="sina")
            memberships = fetch_sina_sector_memberships(sectors)
            membership_rows = store.save_sector_memberships(as_of, memberships)
        except Exception as exc:
            errors.append(f"sina sector snapshots failed: {type(exc).__name__}: {exc}")

    if provider in {"tushare", "tushare-sector"}:
        try:
            sectors = fetch_tushare_sector_fund_flow(selected_date)
            sector_rows = store.save_sector_snapshots(sectors, source="tushare_moneyflow_ind_dc")
        except Exception as exc:
            errors.append(f"tushare sector fund-flow failed: {type(exc).__name__}: {exc}")

    if provider in {"tushare", "tushare-stock"}:
        try:
            moneyflow = fetch_tushare_stock_moneyflow(selected_date)
            moneyflow_rows = store.save_stock_moneyflow(moneyflow, source="tushare_moneyflow_ths")
        except Exception as exc:
            errors.append(f"tushare stock moneyflow failed: {type(exc).__name__}: {exc}")

    if provider in {"instock-em", "instock-em-sector"}:
        try:
            sectors = fetch_instock_all_sector_fund_flow(selected_date)
            sector_rows = store.save_sector_snapshots(sectors, source="instock_eastmoney_sector_moneyflow")
        except Exception as exc:
            errors.append(f"instock eastmoney sector fund-flow failed: {type(exc).__name__}: {exc}")

    if provider in {"instock-em", "instock-em-stock"}:
        try:
            moneyflow = fetch_instock_stock_moneyflow(selected_date)
            moneyflow_rows = store.save_stock_moneyflow(moneyflow, source="instock_eastmoney_stock_moneyflow")
        except Exception as exc:
            errors.append(f"instock eastmoney stock moneyflow failed: {type(exc).__name__}: {exc}")

    if provider in {"auto", "akshare-events", "limit-up-events"}:
        try:
            limit_events, reason_events = fetch_limit_up_events(selected_date)
            limit_up_rows = store.save_limit_up_events(limit_events, source="akshare_stock_zt_pool_em")
            store.delete_news_events(selected_date.isoformat(), "limit_up_reason")
            news_event_rows += store.save_news_events(reason_events)
        except Exception as exc:
            errors.append(f"limit-up events failed: {type(exc).__name__}: {exc}")

    if provider in {"auto", "akshare-events", "dragon-tiger"}:
        try:
            dragon_tiger_events = fetch_dragon_tiger_events(selected_date)
            store.delete_news_events(selected_date.isoformat(), "dragon_tiger")
            news_event_rows += store.save_news_events(dragon_tiger_events)
        except Exception as exc:
            errors.append(f"dragon tiger events failed: {type(exc).__name__}: {exc}")

    if sectors and akshare_sectors_loaded:
        try:
            memberships = fetch_sector_memberships(sectors, per_type_limit=membership_limit)
            membership_rows += store.save_sector_memberships(as_of, memberships)
        except Exception as exc:
            errors.append(f"sector memberships failed: {type(exc).__name__}: {exc}")

    if provider in {"auto", "derived-features", "instock-em", "instock-em-stock"}:
        try:
            stock_inputs = (
                store.load_stock_snapshots_by_trade_date(selected_date.isoformat())
                if trade_date
                else store.load_latest_stock_snapshots()
            )
            moneyflow_inputs = (
                store.load_moneyflow_dicts_by_trade_date(selected_date.isoformat(), limit=20_000)
                if trade_date
                else store.load_latest_moneyflow_dicts(limit=20_000)
            )
            features, rush_events = build_stock_features(
                stock_inputs,
                moneyflow_inputs,
            )
            feature_rows = store.save_stock_features(features)
            store.delete_news_events(selected_date.isoformat(), "rush_accumulation")
            rush_event_rows = store.save_news_events(rush_events)
            news_event_rows += rush_event_rows
        except Exception as exc:
            errors.append(f"derived stock features failed: {type(exc).__name__}: {exc}")

    return {
        "as_of": as_of.isoformat(),
        "trade_date": selected_date.isoformat(),
        "provider": provider,
        "db_path": str(store.db_path),
        "stock_rows": stock_rows,
        "realtime_rows": realtime_rows,
        "moneyflow_rows": moneyflow_rows,
        "sector_rows": sector_rows,
        "membership_rows": membership_rows,
        "limit_up_rows": limit_up_rows,
        "news_event_rows": news_event_rows,
        "feature_rows": feature_rows,
        "rush_event_rows": rush_event_rows,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync A-share market snapshots into local SQLite.")
    parser.add_argument("--db-path", default=None, help="SQLite path. Defaults to RICH_DB_PATH or data/rich.sqlite3.")
    parser.add_argument(
        "--provider",
        choices=[
            "auto",
            "akshare",
            "baostock",
            "sina",
            "sina-sector",
            "tushare",
            "tushare-sector",
            "tushare-stock",
            "instock-em",
            "instock-em-sector",
            "instock-em-stock",
            "akshare-events",
            "limit-up-events",
            "dragon-tiger",
            "derived-features",
        ],
        default="auto",
        help="Data provider. auto tries AKShare/Eastmoney, Baostock daily bars, then Sina realtime if symbols exist.",
    )
    parser.add_argument("--trade-date", default=None, help="Trade date for Baostock daily bars, YYYY-MM-DD.")
    parser.add_argument("--max-symbols", type=int, default=None, help="Limit Baostock symbols for test runs.")
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbols for Sina, e.g. 600000.SH,000001.SZ. Defaults to latest local symbols.",
    )
    parser.add_argument(
        "--membership-limit",
        type=int,
        default=8,
        help="Number of top concept/industry sectors to fetch constituents for.",
    )
    args = parser.parse_args()
    parsed_trade_date = date.fromisoformat(args.trade_date) if args.trade_date else None
    parsed_symbols = [item.strip() for item in args.symbols.split(",") if item.strip()] or None
    result = sync_market_data(
        db_path=args.db_path,
        membership_limit=args.membership_limit,
        provider=args.provider,
        trade_date=parsed_trade_date,
        max_symbols=args.max_symbols,
        symbols=parsed_symbols,
    )
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
