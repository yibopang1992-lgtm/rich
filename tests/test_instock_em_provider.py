from __future__ import annotations

from datetime import date, datetime

from ashare_agent.data_sources import instock_em_provider as provider
from ashare_agent.models import SectorType


def test_instock_stock_moneyflow_maps_eastmoney_fields(monkeypatch) -> None:
    def fake_fetch_pages(*args, **kwargs):
        assert args[0] == "http://push2.eastmoney.com/api/qt/clist/get"
        assert kwargs["include_cookie"] is False
        return [
            {
                "f12": "002281",
                "f14": "光迅科技",
                "f2": 65.2,
                "f3": 6.8,
                "f62": 123456789,
                "f184": 5.6,
                "f66": 111,
                "f72": 222,
                "f124": int(datetime(2026, 7, 15, 10, 26, tzinfo=provider.CN_TZ).timestamp()),
            }
        ]

    monkeypatch.setattr(provider, "fetch_pages", fake_fetch_pages)

    rows = provider.fetch_instock_stock_moneyflow(date(2026, 7, 15))

    assert len(rows) == 1
    assert rows[0].symbol == "002281.SZ"
    assert rows[0].name == "光迅科技"
    assert rows[0].price == 65.2
    assert rows[0].main_net_inflow == 123456789
    assert rows[0].large_order_net_inflow == 222
    assert rows[0].super_large_order_net_inflow == 111
    assert rows[0].timestamp.hour == 10
    assert rows[0].timestamp.minute == 26


def test_instock_sector_moneyflow_maps_concept_fields(monkeypatch) -> None:
    def fake_fetch_pages(*args, **kwargs):
        assert args[0] == "http://80.push2.eastmoney.com/api/qt/clist/get"
        assert kwargs.get("callback_jsonp") is not True
        assert kwargs["include_cookie"] is False
        return [
            {
                "f14": "CPO",
                "f2": 100,
                "f3": 3.2,
                "f62": 987654321,
                "f184": 8.8,
                "f205": "300308",
                "f124": int(datetime(2026, 7, 15, 10, 27, tzinfo=provider.CN_TZ).timestamp()),
            }
        ]

    monkeypatch.setattr(provider, "fetch_pages", fake_fetch_pages)

    rows = provider.fetch_instock_sector_fund_flow(date(2026, 7, 15), SectorType.CONCEPT)

    assert len(rows) == 1
    assert rows[0].sector_name == "CPO"
    assert rows[0].sector_type == SectorType.CONCEPT
    assert rows[0].main_net_inflow == 987654321
    assert rows[0].top_symbols == ["300308.SZ"]
    assert rows[0].breadth == 0
    assert rows[0].timestamp.hour == 10
    assert rows[0].timestamp.minute == 27
