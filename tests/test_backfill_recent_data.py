from __future__ import annotations

from datetime import date

from ashare_agent.data_sources.mock import MockMarketDataProvider
from ashare_agent.scripts import backfill_recent_data as backfill
from ashare_agent.models import SectorSnapshot, SectorType


def test_backfill_skips_historical_current_moneyflow(monkeypatch, tmp_path) -> None:
    mock = MockMarketDataProvider()
    calls = {"moneyflow": 0, "sector_flow": 0}

    monkeypatch.setattr(backfill, "recent_trade_dates", lambda end_date, days: [date(2026, 7, 14), date(2026, 7, 15)])
    monkeypatch.setattr(
        backfill,
        "fetch_eastmoney_daily_snapshots_range",
        lambda start_date, end_date, max_symbols=None, progress=None, stock_rows=None: [
            item.model_copy(
                update={"timestamp": item.timestamp.replace(year=trade_date.year, month=trade_date.month, day=trade_date.day)}
            )
            for trade_date in [date(2026, 7, 14), date(2026, 7, 15)]
            for item in mock.get_stock_snapshots()
        ],
    )
    monkeypatch.setattr(backfill, "fetch_baostock_daily_snapshots", lambda trade_date, max_symbols=None: [])
    monkeypatch.setattr(backfill, "fetch_limit_up_events", lambda trade_date: ([], []))
    monkeypatch.setattr(backfill, "fetch_dragon_tiger_events", lambda trade_date: [])

    def fake_moneyflow(trade_date):
        calls["moneyflow"] += 1
        return [mock.get_stock_snapshots()[0].model_copy(update={"timestamp": mock.as_of.replace(day=trade_date.day)})]

    def fake_sector_flow(trade_date):
        calls["sector_flow"] += 1
        return [
            SectorSnapshot(
                sector_id="test",
                sector_name="测试",
                sector_type=SectorType.CONCEPT,
                timestamp=mock.as_of.replace(day=trade_date.day),
                pct_change=1,
                main_net_inflow=1,
                amount=1,
                amount_growth=0,
                up_count=1,
                down_count=0,
                limit_up_count=0,
                breadth=0.5,
            )
        ]

    monkeypatch.setattr(backfill, "fetch_instock_stock_moneyflow", fake_moneyflow)
    monkeypatch.setattr(backfill, "fetch_instock_all_sector_fund_flow", fake_sector_flow)

    result = backfill.backfill_recent_data(
        db_path=str(tmp_path / "market.sqlite3"),
        days=2,
        end_date=date(2026, 7, 15),
    )

    assert calls == {"moneyflow": 1, "sector_flow": 1}
    assert result["trade_dates"] == ["2026-07-14", "2026-07-15"]
    assert any("2026-07-14" in item for item in result["warnings"])
    assert result["feature_rows"] > 0
