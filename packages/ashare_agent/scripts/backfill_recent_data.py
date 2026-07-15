from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ashare_agent.data_sources.akshare_provider import fetch_dragon_tiger_events, fetch_limit_up_events
from ashare_agent.data_sources.baostock_provider import fetch_baostock_daily_snapshots
from ashare_agent.data_sources.eastmoney_history_provider import fetch_eastmoney_daily_snapshots_range
from ashare_agent.data_sources.instock_em_provider import (
    fetch_instock_all_sector_fund_flow,
    fetch_instock_stock_moneyflow,
)
from ashare_agent.settings import get_db_path
from ashare_agent.storage.sqlite_store import SQLiteMarketStore
from ashare_agent.strategy.features import build_stock_features


CN_TZ = ZoneInfo("Asia/Shanghai")


def recent_trade_dates(end_date: date, days: int) -> list[date]:
    try:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            raise RuntimeError(login.error_msg)
        try:
            start_date = end_date - timedelta(days=max(14, days * 3))
            rs = bs.query_trade_dates(start_date=start_date.isoformat(), end_date=end_date.isoformat())
            trade_dates: list[date] = []
            while rs.next():
                row = dict(zip(rs.fields, rs.get_row_data(), strict=True))
                if row.get("is_trading_day") == "1":
                    trade_dates.append(date.fromisoformat(row["calendar_date"]))
            return trade_dates[-days:]
        finally:
            bs.logout()
    except Exception:
        candidates = []
        cursor = end_date
        while len(candidates) < days:
            if cursor.weekday() < 5:
                candidates.append(cursor)
            cursor -= timedelta(days=1)
        return sorted(candidates)


def backfill_recent_data(
    db_path: str | None = None,
    days: int = 5,
    end_date: date | None = None,
    max_symbols: int | None = None,
    include_today_moneyflow: bool = True,
) -> dict[str, object]:
    selected_end = end_date or datetime.now(CN_TZ).date()
    dates = recent_trade_dates(selected_end, days)
    store = SQLiteMarketStore(db_path or get_db_path())
    store.init_db()

    totals = {
        "stock_rows": 0,
        "limit_up_rows": 0,
        "news_event_rows": 0,
        "moneyflow_rows": 0,
        "sector_rows": 0,
        "feature_rows": 0,
        "rush_event_rows": 0,
    }
    per_day: list[dict[str, object]] = []
    warnings: list[str] = []

    stock_rows_by_date: dict[str, int] = {}
    try:
        print(
            f"[backfill] Eastmoney history daily snapshots start {dates[0].isoformat()}..{dates[-1].isoformat()}",
            flush=True,
        )

        def progress(done: int, total: int) -> None:
            print(f"[backfill] Eastmoney history progress {done}/{total}", flush=True)

        local_universe = [
            {"代码": item.symbol.split(".")[0], "名称": item.name, "总市值": item.market_cap}
            for item in store.load_latest_stock_snapshots()
        ]
        if local_universe:
            print(f"[backfill] using local SQLite stock universe rows={len(local_universe)}", flush=True)

        range_stocks = fetch_eastmoney_daily_snapshots_range(
            dates[0],
            dates[-1],
            max_symbols=max_symbols,
            progress=progress,
            stock_rows=local_universe or None,
        )
        stocks_by_date: dict[str, list] = {}
        for item in range_stocks:
            stocks_by_date.setdefault(item.timestamp.date().isoformat(), []).append(item)
        for trade_date_text, rows_for_day in sorted(stocks_by_date.items()):
            rows = store.save_stock_snapshots(rows_for_day, source="eastmoney_history_kline")
            stock_rows_by_date[trade_date_text] = rows
            totals["stock_rows"] += rows
            print(f"[backfill] {trade_date_text} Eastmoney history rows={rows}", flush=True)
    except Exception as exc:
        warnings.append(f"eastmoney history backfill failed: {type(exc).__name__}: {exc}")

    for trade_date in dates:
        day_result: dict[str, object] = {"trade_date": trade_date.isoformat(), "errors": []}
        errors: list[str] = day_result["errors"]  # type: ignore[assignment]

        if stock_rows_by_date.get(trade_date.isoformat(), 0) > 0:
            day_result["stock_rows"] = stock_rows_by_date[trade_date.isoformat()]
        else:
            print(f"[backfill] {trade_date.isoformat()} baostock daily snapshots fallback start", flush=True)
            try:
                stocks = fetch_baostock_daily_snapshots(trade_date, max_symbols=max_symbols)
                stock_rows = store.save_stock_snapshots(stocks, source="baostock_backfill")
                totals["stock_rows"] += stock_rows
                day_result["stock_rows"] = stock_rows
                print(f"[backfill] {trade_date.isoformat()} baostock daily snapshots rows={stock_rows}", flush=True)
            except Exception as exc:
                errors.append(f"baostock daily backfill failed: {type(exc).__name__}: {exc}")
                day_result["stock_rows"] = 0

        try:
            print(f"[backfill] {trade_date.isoformat()} limit-up events start", flush=True)
            limit_events, reason_events = fetch_limit_up_events(trade_date)
            limit_rows = store.save_limit_up_events(limit_events, source="akshare_stock_zt_pool_em")
            store.delete_news_events(trade_date.isoformat(), "limit_up_reason")
            reason_rows = store.save_news_events(reason_events)
            totals["limit_up_rows"] += limit_rows
            totals["news_event_rows"] += reason_rows
            day_result["limit_up_rows"] = limit_rows
            day_result["limit_up_reason_rows"] = reason_rows
            print(
                f"[backfill] {trade_date.isoformat()} limit-up rows={limit_rows} reasons={reason_rows}",
                flush=True,
            )
        except Exception as exc:
            errors.append(f"limit-up events failed: {type(exc).__name__}: {exc}")
            day_result["limit_up_rows"] = 0
            day_result["limit_up_reason_rows"] = 0

        try:
            print(f"[backfill] {trade_date.isoformat()} dragon-tiger events start", flush=True)
            dragon_tiger_events = fetch_dragon_tiger_events(trade_date)
            store.delete_news_events(trade_date.isoformat(), "dragon_tiger")
            dragon_rows = store.save_news_events(dragon_tiger_events)
            totals["news_event_rows"] += dragon_rows
            day_result["dragon_tiger_rows"] = dragon_rows
            print(f"[backfill] {trade_date.isoformat()} dragon-tiger rows={dragon_rows}", flush=True)
        except Exception as exc:
            errors.append(f"dragon tiger events failed: {type(exc).__name__}: {exc}")
            day_result["dragon_tiger_rows"] = 0

        if include_today_moneyflow and trade_date == selected_end:
            try:
                print(f"[backfill] {trade_date.isoformat()} Eastmoney stock moneyflow start", flush=True)
                moneyflow = fetch_instock_stock_moneyflow(trade_date)
                moneyflow_rows = store.save_stock_moneyflow(moneyflow, source="instock_eastmoney_stock_moneyflow")
                totals["moneyflow_rows"] += moneyflow_rows
                day_result["moneyflow_rows"] = moneyflow_rows
                print(f"[backfill] {trade_date.isoformat()} Eastmoney stock moneyflow rows={moneyflow_rows}", flush=True)
            except Exception as exc:
                errors.append(f"eastmoney stock moneyflow failed: {type(exc).__name__}: {exc}")
                day_result["moneyflow_rows"] = 0

            try:
                print(f"[backfill] {trade_date.isoformat()} Eastmoney sector fundflow start", flush=True)
                sectors = fetch_instock_all_sector_fund_flow(trade_date)
                sector_rows = store.save_sector_snapshots(sectors, source="instock_eastmoney_sector_moneyflow")
                totals["sector_rows"] += sector_rows
                day_result["sector_rows"] = sector_rows
                print(f"[backfill] {trade_date.isoformat()} Eastmoney sector rows={sector_rows}", flush=True)
            except Exception as exc:
                errors.append(f"eastmoney sector fundflow failed: {type(exc).__name__}: {exc}")
                day_result["sector_rows"] = 0
        else:
            warnings.append(
                f"{trade_date.isoformat()}: skipped Eastmoney current money-flow endpoint to avoid historical mislabeling"
            )
            day_result["moneyflow_rows"] = 0
            day_result["sector_rows"] = 0

        try:
            print(f"[backfill] {trade_date.isoformat()} derived features start", flush=True)
            features, rush_events = build_stock_features(
                store.load_stock_snapshots_by_trade_date(trade_date.isoformat()),
                store.load_moneyflow_dicts_by_trade_date(trade_date.isoformat(), limit=20_000),
            )
            feature_rows = store.save_stock_features(features)
            store.delete_news_events(trade_date.isoformat(), "rush_accumulation")
            rush_rows = store.save_news_events(rush_events)
            totals["feature_rows"] += feature_rows
            totals["rush_event_rows"] += rush_rows
            totals["news_event_rows"] += rush_rows
            day_result["feature_rows"] = feature_rows
            day_result["rush_event_rows"] = rush_rows
            print(
                f"[backfill] {trade_date.isoformat()} feature rows={feature_rows} rush_events={rush_rows}",
                flush=True,
            )
        except Exception as exc:
            errors.append(f"derived features failed: {type(exc).__name__}: {exc}")
            day_result["feature_rows"] = 0
            day_result["rush_event_rows"] = 0

        per_day.append(day_result)

    return {
        "as_of": datetime.now(CN_TZ).isoformat(),
        "db_path": str(store.db_path),
        "trade_dates": [item.isoformat() for item in dates],
        **totals,
        "warnings": sorted(set(warnings)),
        "per_day": per_day,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill recent A-share daily data, events, and features.")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--days", type=int, default=5)
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD, defaults to today.")
    parser.add_argument("--max-symbols", type=int, default=None, help="Limit stock universe for tests.")
    parser.add_argument("--skip-today-moneyflow", action="store_true")
    args = parser.parse_args()

    result = backfill_recent_data(
        db_path=args.db_path,
        days=args.days,
        end_date=date.fromisoformat(args.end_date) if args.end_date else None,
        max_symbols=args.max_symbols,
        include_today_moneyflow=not args.skip_today_moneyflow,
    )
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
