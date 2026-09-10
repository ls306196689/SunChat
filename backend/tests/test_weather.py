"""
增补：天气直查测试（离线：monkeypatch 网络层）
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.weather import is_weather_query, _to_cities, get_weather_context

FAKE_WTTR = {
    "current_condition": [{
        "temp_C": "19", "FeelsLikeC": "18", "humidity": "52",
        "windspeedKmph": "4", "visibility": "6", "uvIndex": "0",
        "weatherDesc": [{"value": "Smoky haze"}],
    }],
    "nearest_area": [{
        "areaName": [{"value": "Beijing"}], "region": [{"value": ""}],
    }],
    "weather": [{"maxtempC": "22", "mintempC": "15"}],
}


class TestWeatherDetect:
    def test_is_weather_query(self):
        assert is_weather_query("今天北京的天气怎么样")
        assert is_weather_query("明天下雨吗")
        assert is_weather_query("上海气温多少")
        assert not is_weather_query("今天有什么新闻")

    def test_to_cities(self):
        assert _to_cities("看下今天北京的天气") == ["Beijing"]
        assert _to_cities("上海和北京天气") == ["Shanghai", "Beijing"]
        assert _to_cities("Paris weather") == ["Paris"]
        assert _to_cities("今天天气怎么样") == []  # 无城市 → 不 IP 定位,回退搜索(D-004)


class TestWeatherFetch:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        # R-007: 城市级TTL缓存引入跨用例状态,失败类用例需纯净缓存态
        from core.weather import clear_weather_cache
        clear_weather_cache()
        yield
        clear_weather_cache()

    def test_parse_wttr(self, monkeypatch):
        calls = []

        class Resp:
            status_code = 200

            def json(self):
                return FAKE_WTTR

        monkeypatch.setattr("core.weather.requests.get",
                            lambda url, headers=None, timeout=None:
                            calls.append(url) or Resp())

        ctx = get_weather_context("北京天气")
        assert ctx is not None
        assert "Beijing" in ctx and "19°C" in ctx and "烟霾" in ctx
        assert "22°C" in ctx and "15°C" in ctx
        assert "wttr.in/Beijing" in calls[0]

    def test_non_weather_returns_none(self, monkeypatch):
        called = []
        monkeypatch.setattr("core.weather.requests.get",
                            lambda *a, **kw: called.append(1))
        assert get_weather_context("今天新闻") is None
        assert not called

    def test_no_city_returns_none_without_request(self, monkeypatch):
        """D-004: 天气问法但无城市 → None 且不发网络请求(不做 IP 定位)"""
        called = []
        monkeypatch.setattr("core.weather.requests.get",
                            lambda *a, **kw: called.append(1))
        assert get_weather_context("今天天气怎么样") is None
        assert not called

    def test_network_fail_returns_none(self, monkeypatch):
        def boom(*a, **kw):
            raise ConnectionError("proxy down")
        monkeypatch.setattr("core.weather.requests.get", boom)
        assert get_weather_context("北京天气") is None

    def test_http_error_returns_none(self, monkeypatch):
        class Resp:
            status_code = 500

            def json(self):
                return {}
        monkeypatch.setattr("core.weather.requests.get",
                            lambda *a, **kw: Resp())
        assert get_weather_context("北京天气") is None


class TestAgentTool:
    def test_get_weather_tool_registered(self):
        from core.agent.tools import get_tool
        td = get_tool("get_weather")
        assert td and "city" in td.parameters["properties"]

    def test_execute_tool_no_user_id_injection(self, monkeypatch):
        """web_search/get_weather 签名无 user_id，框架不得注入（历史 bug）"""
        from core.agent.tools import execute_tool

        class Resp:
            status_code = 200

            def json(self):
                return FAKE_WTTR
        monkeypatch.setattr("core.weather.requests.get",
                            lambda *a, **kw: Resp())
        r = execute_tool("get_weather", {"city": "北京", "user_id": 999}, user_id=1)
        assert r.success and "Beijing" in r.data

    def test_signed_tool_user_id_injection_not_regressed(self, monkeypatch):
        """R-002/AC-2: 签名接受 user_id 的工具(memory_search)仍强制注入会话 user_id,
        LLM 伪造的 user_id 一律丢弃,防越权不回退。"""
        from core.agent.tools import execute_tool

        captured = {}

        def fake_search_memories(user_id=None, query=None, top_k=5):
            captured["user_id"] = user_id
            return []
        monkeypatch.setattr("core.agent.tools.memory_service.search_memories",
                            fake_search_memories)
        execute_tool("memory_search", {"query": "x", "user_id": 999}, user_id=42)
        assert captured["user_id"] == 42
