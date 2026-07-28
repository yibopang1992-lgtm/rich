from __future__ import annotations

from datetime import datetime

from ashare_agent.data_sources import akshare_provider as provider
from ashare_agent.models import SectorSnapshot, SectorType


def test_fetch_sector_memberships_prefers_eastmoney_board_code(monkeypatch) -> None:
    sector = SectorSnapshot(
        sector_id="instock_em_concept_BK1234",
        sector_name="测试板块",
        sector_type=SectorType.CONCEPT,
        timestamp=datetime.now(provider.CN_TZ),
        pct_change=5,
        main_net_inflow=1,
        amount=1,
        amount_growth=0,
        up_count=1,
        down_count=0,
        limit_up_count=0,
        breadth=1,
    )

    monkeypatch.setattr(
        provider,
        "fetch_eastmoney_sector_memberships",
        lambda item, board_code: [
            {
                "sector_name": item.sector_name,
                "sector_type": item.sector_type.value,
                "symbol": "300663.SZ",
                "name": board_code,
            }
        ],
    )

    rows = provider.fetch_sector_memberships([sector], per_type_limit=1)

    assert rows == [
        {
            "sector_name": "测试板块",
            "sector_type": "concept",
            "symbol": "300663.SZ",
            "name": "BK1234",
        }
    ]

