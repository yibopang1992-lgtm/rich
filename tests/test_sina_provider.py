from __future__ import annotations

from ashare_agent.data_sources.sina_provider import from_sina_code, to_sina_code


def test_sina_symbol_conversion() -> None:
    assert to_sina_code("600000.SH") == "sh600000"
    assert to_sina_code("000001.SZ") == "sz000001"
    assert from_sina_code("sh600000") == "600000.SH"
    assert from_sina_code("sz000001") == "000001.SZ"
