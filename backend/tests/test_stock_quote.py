"""
S-增补：股价直查测试（离线：monkeypatch 网络层）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.stock import is_stock_query, _to_symbols, get_stock_context

# 腾讯 usBABA 真实响应（字段错位会导致解析失败，必须与真实结构一致）
FAKE_TENCENT = (
    'v_usBABA="200~阿里巴巴~BABA.N~113.24~111.81~112.37~7182522~0~0~113.01~100~'
    '0~0~0~0~0~0~0~0~113.18~100~0~0~0~0~0~0~0~0~~2026-09-04 16:04:38~1.43~1.28~'
    '113.41~111.97~USD~7182522~810867596~0.29~25.89~~17.76~1:8~1.29~2765.24284~'
    '2814.72018~Alibaba Group Holding Ltd~4.37~191.62~91.99~0~1.80~0.91~'
    '2814.72018~-22.19~-4.76~GP~7.07~3.83~-5.11~-11.81~-0.95~2485623615~'
    '2441931152~0.81~52.20~1.03~112.89~~~";'
)


class TestStockDetect:
    def test_is_stock_query(self):
        assert is_stock_query("阿里巴巴今天股价")
        assert is_stock_query("BABA行情怎么看")
        assert not is_stock_query("今天有什么新闻")

    def test_to_symbols(self):
        assert _to_symbols("阿里巴巴BABA今天股价") == ["usBABA"]
        assert _to_symbols("09988股价") == ["hk09988"]
        assert _to_symbols("600519茅台股价") == ["sh600519"]
        assert _to_symbols("000001股价") == ["sz000001"]
        # 纯中文公司名不提取（回退普通搜索）
        assert _to_symbols("阿里巴巴的股价") == []
        # API/AI 等噪音词不算代码
        assert _to_symbols("API的AI股价") == []


class TestStockFetch:
    def test_parse_tencent_quote(self, monkeypatch):
        class Resp:
            status_code = 200
            text = FAKE_TENCENT
            encoding = "gbk"

        calls = []

        def fake_get(url, headers=None, timeout=None):
            calls.append(url)
            return Resp()
        import core.stock as stock_mod
        monkeypatch.setattr(stock_mod.requests, "get", fake_get)

        ctx = get_stock_context("BABA股价")
        assert ctx is not None
        assert "113.24" in ctx and "+1.28%" in ctx and "美股" in ctx and "USD" in ctx

    def test_non_stock_returns_none(self, monkeypatch):
        raise_called = []
        import core.stock as stock_mod

        def boom(*a, **kw):
            raise_called.append(1)
        monkeypatch.setattr(stock_mod.requests, "get", boom)
        assert get_stock_context("今天新闻") is None   # 非股价不请求
        assert not raise_called
        # 股价但无代码 → None（不请求不报错）
        assert get_stock_context("股价一般怎么看") is None

    def test_network_fail_returns_none(self, monkeypatch):
        import core.stock as stock_mod

        def boom(*a, **kw):
            raise ConnectionError("proxy down")
        monkeypatch.setattr(stock_mod.requests, "get", boom)
        assert get_stock_context("BABA股价") is None

    def test_search_with_introduction_uses_stock(self, monkeypatch):
        """股价问题走 search_with_introduction → answer 上下文含实时价、sources 首位为行情"""
        from services import search_service as ss_mod
        import core.stock as stock_mod

        class Resp:
            text = FAKE_TENCENT
            encoding = "gbk"
        monkeypatch.setattr(stock_mod.requests, "get",
                            lambda *a, **kw: Resp())
        # LLM 归纳回退路径：直接检查传入 context 拼装
        captured = {}

        def fake_generate_answer(query, context, memories):
            captured["context"] = context
            return "BABA 最新 113.24 美元"
        monkeypatch.setattr(ss_mod.search_svc, "_generate_answer", fake_generate_answer)

        result = ss_mod.search_svc.search_with_introduction("BABA今天股价")
        assert "113.24" in captured["context"]
        assert result["sources"][0]["source"] == "tencent-quote"
        assert "113.24" in result["answer"]
