"""
R-007: 资源与数据层加固 - DB索引(AC-1) / 提取线程池上限(AC-2) / 天气&行情TTL缓存(AC-3,AC-4)
见 R-007/requirements.md
"""
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDbIndexes:
    """R-007/AC-1: ensure_schema 后热列索引齐全且幂等(每模块经 conftest 独立DB)"""

    EXPECTED = {
        "messages": {"session_id", "created_at"},
        "chat_sessions": {"user_id"},
        "memories": {"user_id"},
        "kb_chunks": {"file_id"},
        "search_history": {"user_id"},
    }

    def _idx_map(self):
        from sqlalchemy import inspect
        from models.sql_models import get_engine
        insp = inspect(get_engine())
        return {t: {tuple(ix["column_names"]) for ix in insp.get_indexes(t)}
                for t in self.EXPECTED}

    def test_hot_indexes_exist(self):
        from models.sql_models import ensure_schema
        ensure_schema()
        m = self._idx_map()
        assert ("session_id", "created_at") in m["messages"], "messages 复合热索引缺失"
        for t, col in [("chat_sessions", "user_id"), ("memories", "user_id"),
                       ("kb_chunks", "file_id"), ("search_history", "user_id")]:
            assert (col,) in m[t], f"{t}.{col} 索引缺失"
        # memories(user_id, is_active) 复合
        assert ("user_id", "is_active") in m["memories"]

    def test_ensure_schema_idempotent(self):
        from models.sql_models import ensure_schema
        ensure_schema()
        ensure_schema()  # 重复执行无错(IF NOT EXISTS)
        m = self._idx_map()
        assert ("session_id", "created_at") in m["messages"]


class TestExtractorPoolBounded:
    """R-007/AC-2: 提取线程池 max_workers=2 + 在途上限8,超限丢弃"""

    def test_pool_drops_over_limit(self, monkeypatch):
        from services.chat_service import ChatService
        svc = ChatService.__new__(ChatService)  # 不触 DB
        svc.__init__()

        started = threading.Event()
        n_submit = []

        def fake_apply(*a, **k):
            n_submit.append(1)
            started.wait(timeout=5)

        monkeypatch.setattr(svc, "apply_memory_extraction", fake_apply)

        futures = []
        for i in range(8):
            f = svc.extract_memories_async(1, f"m{i}", "r", [])
            futures.append(f)
        assert len(futures) == 8, "在途8个应全部受理(2跑6排队)"
        # 排队任务需 worker 空出才启动;再提交第9个 → 丢弃
        f9 = svc.extract_memories_async(1, "m9", "r", [])
        assert f9 is None, "第9个在途应被丢弃"

        started.set()
        for f in futures:
            f.result(timeout=10)
        # 在途归零后可继续受理
        started2 = threading.Event()
        monkeypatch.setattr(svc, "apply_memory_extraction",
                            lambda *a, **k: started2.set())
        started2.clear()
        f10 = svc.extract_memories_async(1, "m10", "r", [])
        assert f10 is not None, "归零后应恢复受理"
        f10.result(timeout=10)

    def test_workers_bounded_2(self):
        from services.chat_service import ChatService
        assert ChatService._extract_workers == 2
        assert ChatService._extract_max_inflight == 8

    def test_inflight_decrements_after_failure(self, monkeypatch):
        from services.chat_service import ChatService
        svc = ChatService.__new__(ChatService)
        svc.__init__()

        def boom(*a, **k):
            raise RuntimeError("llm down")
        monkeypatch.setattr(svc, "apply_memory_extraction", boom)
        f = svc.extract_memories_async(1, "m", "r", [])
        f.result(timeout=5)  # 异常在线程内吞并记日志
        time.sleep(0.05)
        assert svc._extract_inflight == 0, "失败后在途计数必须归零"


class TestWeatherCache:
    """R-007/AC-3: 城市级 TTL 缓存,失败不缓存"""

    def _fake_ok(self, monkeypatch, counter):
        import core.weather as w

        class R:
            status_code = 200

            def json(self):
                return {"current_condition": [{"weatherDesc": [{"value": "Sunny"}],
                                               "temp_C": "20", "FeelsLikeC": "19",
                                               "humidity": "50", "windspeedKmph": "10",
                                               "visibility": "10", "uvIndex": "5"}],
                        "nearest_area": [{}], "weather": [{}]}
        def fake_get(url, **kw):
            counter.append(url)
            return R()
        monkeypatch.setattr(w.requests, "get", fake_get)
        w.clear_weather_cache()

    def test_second_call_served_from_cache(self, monkeypatch):
        import core.weather as w
        n = []
        self._fake_ok(monkeypatch, n)
        t1 = w.get_weather_context("北京天气")
        t2 = w.get_weather_context("北京天气")
        assert t1 and t2 and len(n) == 1, "TTL 内同城市应仅1次外网请求"
        w.clear_weather_cache()

    def test_failure_not_cached(self, monkeypatch):
        import core.weather as w
        n = []

        def fake_get(url, **kw):
            n.append(url)
            raise ConnectionError("wttr down")
        monkeypatch.setattr(w.requests, "get", fake_get)
        w.clear_weather_cache()
        assert w.get_weather_context("北京天气") is None
        assert w.get_weather_context("北京天气") is None
        assert len(n) == 2, "失败不入缓存,每次重试"
        w.clear_weather_cache()

    def test_ttl_expiry(self, monkeypatch):
        import core.weather as w
        n = []
        self._fake_ok(monkeypatch, n)
        w.clear_weather_cache()
        w.get_weather_context("北京天气")
        monkeypatch.setattr(w, "_CACHE_TTL", 0)  # 立即过期
        w.get_weather_context("北京天气")
        assert len(n) == 2, "TTL 过期后应重新拉取"
        w.clear_weather_cache()


class TestStockCache:
    """R-007/AC-4: symbols 级 TTL 缓存,失败不缓存"""

    def test_second_call_served_from_cache(self, monkeypatch):
        import core.stock as st
        n = []

        def fake_fetch(symbols):
            n.append(tuple(symbols))
            return [{"name": "腾讯", "code": "00700", "market": "港股",
                     "currency": "HKD", "price": 400.0, "change": 1.0, "pct": 0.25,
                     "open": 399, "prev_close": 399, "high": 401, "low": 398,
                     "time": "20260911"}]
        monkeypatch.setattr(st, "_fetch_tencent", fake_fetch)
        st.clear_stock_cache()
        c1 = st.get_stock_context("腾讯股价")
        c2 = st.get_stock_context("腾讯的股票现在多少钱")  # 不同问法同 symbols
        assert c1 and c2 and len(n) == 1

    def test_failure_not_cached(self, monkeypatch):
        import core.stock as st
        n = []

        def boom(symbols):
            n.append(1)
            raise ConnectionError("down")
        monkeypatch.setattr(st, "_fetch_tencent", boom)
        st.clear_stock_cache()
        assert st.get_stock_context("腾讯股价") is None
        assert st.get_stock_context("腾讯股价") is None
        assert len(n) == 2
