from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace

import pandas as pd

from ashare_agent.data_sources.akshare_provider import fetch_dragon_tiger_events, fetch_limit_up_events


def test_fetch_limit_up_events_maps_akshare_rows(monkeypatch) -> None:
    fake_akshare = SimpleNamespace(
        stock_zt_pool_em=lambda date: pd.DataFrame(
            [
                {
                    "代码": "002432",
                    "名称": "九安医疗",
                    "涨跌幅": 10.0,
                    "封板资金": 331968945,
                    "首次封板时间": "092500",
                    "炸板次数": 0,
                    "连板数": 2,
                    "所属行业": "医疗器械",
                }
            ]
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    limit_events, news_events = fetch_limit_up_events(date(2026, 7, 15))

    assert limit_events[0].symbol == "002432.SZ"
    assert limit_events[0].first_limit_time == "09:25:00"
    assert limit_events[0].consecutive_boards == 2
    assert news_events[0].event_type == "limit_up_reason"
    assert news_events[0].sectors == ["医疗器械"]


def test_fetch_dragon_tiger_events_maps_akshare_rows(monkeypatch) -> None:
    fake_akshare = SimpleNamespace(
        stock_lhb_detail_em=lambda start_date, end_date: pd.DataFrame(
            [
                {
                    "代码": "000566",
                    "名称": "海南海药",
                    "解读": "上海资金买入",
                    "龙虎榜净买额": 78781830,
                    "龙虎榜成交额": 161258000,
                    "成交额占总成交比": 29.95,
                    "换手率": 8.37,
                    "上榜原因": "日振幅值达到15%的前5只证券",
                }
            ]
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    events = fetch_dragon_tiger_events(date(2026, 7, 15))

    assert events[0].symbols == ["000566.SZ"]
    assert events[0].event_type == "dragon_tiger"
    assert events[0].sentiment > 0
    assert "上海资金买入" in events[0].title


def test_fetch_dragon_tiger_events_filters_b_shares(monkeypatch) -> None:
    fake_akshare = SimpleNamespace(
        stock_lhb_detail_em=lambda start_date, end_date: pd.DataFrame(
            [
                {
                    "代码": "200016",
                    "名称": "康佳B",
                    "解读": "普通席位买入",
                    "龙虎榜净买额": 22327,
                    "龙虎榜成交额": 1418948,
                    "成交额占总成交比": 93.24,
                    "换手率": 0.30,
                    "上榜原因": "日涨幅偏离值达到7%的前5只证券",
                }
            ]
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    assert fetch_dragon_tiger_events(date(2026, 7, 15)) == []
