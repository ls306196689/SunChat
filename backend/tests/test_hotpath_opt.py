"""
R-006: 热路径延迟优化 - 行情去重(AC-1) / 轻调用短超时(AC-2) / is_available TTL缓存(AC-3,AC-4)
见 R-006/requirements.md 与 design-change.md
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestStockContextDedup:
    """R-006/AC-1: build_context 行情探测结果透传,最坏路径 get_stock_context 仅 1 次"""

    def test_stock_fail_path_calls_api_once(self, monkeypatch):
        import core.stock as stock_mod
        calls = []

        def fake_get_ctx(q):
            calls.append(q)
            return None  # 探测失败
        monkeypatch.setattr(stock_mod, "is_stock_query", lambda q: True)
        monkeypatch.setattr(stock_mod, "get_stock_context", fake_get_ctx)

        from core.search import search_service as core_search
        monkeypatch.setattr(core_search, "text", lambda *a, **k: [], raising=False)

        from services import search_service as ss_mod
        monkeypatch.setattr(ss_mod.SearchService, "route_query",
                            lambda self, q, m=None: {"intent": "general", "query": q})
        monkeypatch.setattr(ss_mod.SearchService, "search",
                            lambda self, q, intent=None, max_results=5: [])

        def fake_gen(self, query, context, memories=None):
            return "归纳答案"
        monkeypatch.setattr(ss_mod.SearchService, "_generate_answer", fake_gen,
                            raising=False)

        from core.chat_router import chat_router
        monkeypatch.setattr(chat_router, "route",
                            lambda q, context=None: {"tool": "search"})

        from services.chat_service import chat_service
        from core.weather import is_weather_query
        # 行情失败且路由判 search → search_with_introduction 收到 _UNSET?
        # 断言:整条 build_context 路径 get_stock_context 恰好 1 次
        chat_service.build_context(
            user_id="u1", session_id=1, content="腾讯股价多少",
            memory_enabled=False, search_enabled=True)
        assert len(calls) == 1, f"行情 API 应仅调用 1 次,实际 {len(calls)} 次"

    def test_independent_call_default_unchanged(self, monkeypatch):
        # AC-1 回归:独立调用方(不传 stock_context)仍自取行情
        import core.stock as stock_mod
        calls = []
        monkeypatch.setattr(stock_mod, "get_stock_context",
                            lambda q: calls.append(q) or "价格:10")
        from services import search_service as ss_mod
        monkeypatch.setattr(ss_mod.SearchService, "route_query",
                            lambda self, q, m=None: {"intent": "general", "query": q})
        monkeypatch.setattr(ss_mod.SearchService, "search",
                            lambda self, q, intent=None, max_results=5: [])
        monkeypatch.setattr(ss_mod.SearchService, "_generate_answer",
                            lambda self, query, context, memories=None: "答案x")
        result = ss_mod.search_svc.search_with_introduction("腾讯股价")
        assert len(calls) == 1 and "价格:10" in result["sources"][0]["snippet"]

    def test_explicit_context_skips_api(self, monkeypatch):
        import core.stock as stock_mod
        monkeypatch.setattr(stock_mod, "get_stock_context",
                            lambda q: pytest.fail("显式传入后不应再请求行情API"))
        from services import search_service as ss_mod
        monkeypatch.setattr(ss_mod.SearchService, "route_query",
                            lambda self, q, m=None: {"intent": "general", "query": q})
        monkeypatch.setattr(ss_mod.SearchService, "search",
                            lambda self, q, intent=None, max_results=5: [])
        monkeypatch.setattr(ss_mod.SearchService, "_generate_answer",
                            lambda self, query, context, memories=None: "答案y")
        r = ss_mod.search_svc.search_with_introduction("腾讯股价", stock_context="实时:88")
        assert r["sources"][0]["snippet"] == "实时:88"


class TestLightTimeout:
    """R-006/AC-2: 轻调用透传短超时,主生成路径不变"""

    def test_generate_passes_timeout(self, monkeypatch):
        from core import llm as llm_mod
        seen = {}

        def fake_post(url, payload, timeout=None, stream=False):
            seen["timeout"] = timeout

            class R:
                def raise_for_status(self): pass
                def json(self): return {"message": {"content": "ok"}}
            return R()
        monkeypatch.setattr(llm_mod, "_post", fake_post)
        out = llm_mod.ollama_service.generate("p", timeout=20)
        assert out == "ok" and seen["timeout"] == 20

    def test_generate_default_timeout_none(self, monkeypatch):
        from core import llm as llm_mod
        seen = {}

        def fake_post(url, payload, timeout=None, stream=False):
            seen["timeout"] = timeout

            class R:
                def raise_for_status(self): pass
                def json(self): return {"message": {"content": "ok"}}
            return R()
        monkeypatch.setattr(llm_mod, "_post", fake_post)
        llm_mod.ollama_service.generate("p")
        assert seen["timeout"] is None  # 主路径沿用 LLM_TIMEOUT 默认

    def test_memory_router_uses_light_timeout(self, monkeypatch):
        from core import memory_router as mr_mod
        seen = {}

        class FakeLLM:
            def generate(self, prompt, **kw):
                seen.update(kw)
                raise RuntimeError("boom")  # 走回退路径
        monkeypatch.setattr(mr_mod, "ollama_service", FakeLLM())
        router = mr_mod.MemoryRouter()
        monkeypatch.setattr(router, "_fallback_analysis",
                            lambda q: {"needs_memory_query": False,
                                       "recommended_memory_types": [],
                                       "query_keywords": []})
        result = router.analyze_memory_need("请帮我查一下明天上海到北京的航班和沿途天气情况如何",
                                context=None)
        from app.config import settings
        assert seen.get("timeout") == settings.LLM_LIGHT_TIMEOUT
        assert "needs_memory_query" in result  # 回退仍返回结构

    def test_memory_extractor_uses_light_timeout(self, monkeypatch):
        from core import memory_extractor as me_mod
        seen = {}

        class FakeLLM:
            def generate(self, prompt, **kw):
                seen.update(kw)
                return ""
        monkeypatch.setattr(me_mod, "ollama_service", FakeLLM())
        ex = me_mod.MemoryExtractor()
        ex.extract_memories("你好", "你好呀", [])
        from app.config import settings
        assert seen.get("timeout") == settings.LLM_LIGHT_TIMEOUT


class TestHealthAvailabilityCache:
    """R-006/AC-3: is_available TTL 缓存;AC-4: /health 契约不变"""

    def test_is_available_cached_within_ttl(self, monkeypatch):
        from core import model_manager as mm_mod
        mm = mm_mod.ModelManager.__new__(mm_mod.ModelManager)
        mm._avail_flag = None
        mm._avail_ts = 0.0
        mm._avail_ttl = 30
        n = []

        def fake_get(url, timeout=None):
            n.append(1)

            class R:
                status_code = 200
            return R()
        monkeypatch.setattr(mm_mod.requests, "get", fake_get)
        assert mm.is_available() and mm.is_available() and mm.is_available()
        assert len(n) == 1, "TTL 内应仅实探 1 次"

    def test_invalidate_forces_reprobe(self, monkeypatch):
        from core import model_manager as mm_mod
        mm = mm_mod.ModelManager.__new__(mm_mod.ModelManager)
        mm._avail_flag = None
        mm._avail_ts = 0.0
        mm._avail_ttl = 30
        n = []

        def fake_get(url, timeout=None):
            n.append(1)

            class R:
                status_code = 200
            return R()
        monkeypatch.setattr(mm_mod.requests, "get", fake_get)
        mm.is_available()
        mm.invalidate_availability_cache()
        mm.is_available()
        assert len(n) == 2

    def test_failure_result_also_cached(self, monkeypatch):
        from core import model_manager as mm_mod
        mm = mm_mod.ModelManager.__new__(mm_mod.ModelManager)
        mm._avail_flag = None
        mm._avail_ts = 0.0
        mm._avail_ttl = 30
        n = []

        def fake_get(url, timeout=None):
            n.append(1)
            raise ConnectionError("down")
        monkeypatch.setattr(mm_mod.requests, "get", fake_get)
        assert mm.is_available() is False
        assert mm.is_available() is False
        assert len(n) == 1, "失败结果同样缓存,宕机时 /health 不挂 3s×N"

    def test_health_contract(self, client, monkeypatch):
        # AC-4: 字段结构不变
        from core.model_manager import model_manager as mm
        monkeypatch.setattr(mm, "invalidate_availability_cache", lambda: None,
                            raising=False)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for k in ("status", "llm_available", "search_available",
                  "llm_model", "embedding_model", "version"):
            assert k in data
