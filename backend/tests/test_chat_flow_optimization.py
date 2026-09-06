"""
S4 对话降本 / 正确性测试（离线 mock）
覆盖: 问候语 0 路由 LLM、system 单份、多轮历史、搜索接入、真实 token、错误不吞
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fakes
from fakes import CALLS, LAST_CHAT_PAYLOADS, reset_calls


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    reset_calls()
    yield
    reset_calls()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    from models.sql_models import init_db, reset_engine
    reset_engine()
    init_db()
    yield


@pytest.fixture
def service():
    from services.chat_service import ChatService
    return ChatService()


class TestMemoryRouterRuleFirst:
    def test_greeting_zero_llm(self):
        """问候语走规则路径：不产生任何 LLM 调用"""
        from core.memory_router import memory_router
        result = memory_router.analyze_memory_need("你好")
        assert result["needs_memory_query"] is False
        assert CALLS["chat"] == 0

    def test_personal_keyword_rule_hit_zero_llm(self):
        """个人关键词命中：规则直接出结果，不调 LLM"""
        from core.memory_router import memory_router
        result = memory_router.analyze_memory_need("我喜欢什么运动？")
        assert result["needs_memory_query"] is True
        assert CALLS["chat"] == 0


class TestProcessMessageOptimization:
    def _session(self, service, uid):
        return int(service.create_session(user_id=uid)["session_id"])

    def test_single_generation_call(self, service, monkeypatch):
        """一次消息 = 恰 1 次生成 LLM 调用；记忆提取被卸载到后台（不占请求路径）"""
        uid = 5101
        sid = self._session(service, uid)
        called = []
        monkeypatch.setattr(type(service), "extract_memories_async",
                            lambda *a, **kw: called.append(a[1:]))
        reset_calls()
        result = service.process_message(
            user_id=uid, session_id=sid, content="你好", extract_memory_inline=False)
        assert result["response"]
        assert CALLS["chat"] == 1
        assert called, "应调用异步提取卸载（未阻塞等待）"

    def test_async_extraction_persists(self, service):
        """真正的后台线程：轮询等待提取结果最终落库"""
        import time as _t
        uid = 5111
        sid = self._session(service, uid)
        service.extract_memories_async(uid, "我叫林小美", "好的，林小美！", [])
        deadline = _t.time() + 3
        found = 0
        while _t.time() < deadline:
            from services.memory_service import memory_service
            found = memory_service.list_memories(user_id=uid)["total"]
            if found >= 1:
                break
            _t.sleep(0.05)
        assert found >= 1

    def test_system_message_single(self, service):
        """system 只注入一次（messages 中 role=system 仅 1 条）"""
        uid = 5102
        sid = self._session(service, uid)
        service.process_message(user_id=uid, session_id=sid, content="你好",
                                memory_enabled=False, search_enabled=False)
        payload = LAST_CHAT_PAYLOADS[-1]
        roles = [m["role"] for m in payload["messages"]]
        assert roles.count("system") == 1
        # user 内容不再被 system 文本污染
        user_msg = [m for m in payload["messages"] if m["role"] == "user"][-1]
        assert user_msg["content"] == "你好"

    def test_multi_turn_history_injected(self, service):
        """第二轮生成请求包含第一轮历史消息"""
        uid = 5103
        sid = self._session(service, uid)
        service.process_message(user_id=uid, session_id=sid, content="第一句话内容",
                                memory_enabled=False, search_enabled=False)
        reset_calls()
        service.process_message(user_id=uid, session_id=sid, content="第二句话内容",
                                memory_enabled=False, search_enabled=False)
        msgs = LAST_CHAT_PAYLOADS[-1]["messages"]
        contents = " ".join(m["content"] for m in msgs)
        assert "第一句话内容" in contents

    def test_search_enabled_wired(self, service, monkeypatch):
        """search 意图 + 开关开启 → prompt 含搜索结果与来源"""
        uid = 5104
        sid = self._session(service, uid)
        result = service.process_message(
            user_id=uid, session_id=sid, content="最新的新闻是什么",
            memory_enabled=False, search_enabled=True)
        assert result["sources"], "sources 应非空"
        prompt_msgs = LAST_CHAT_PAYLOADS[-1]["messages"]
        system_content = next(m["content"] for m in prompt_msgs if m["role"] == "system")
        assert "联网搜索结果" in system_content
        assert "example.com" in system_content

    def test_search_disabled_no_search(self, service):
        """开关关闭 → 不接入搜索（无 sources，且少一次归纳 LLM）"""
        uid = 5105
        sid = self._session(service, uid)
        result = service.process_message(
            user_id=uid, session_id=sid, content="最新的新闻是什么",
            memory_enabled=False, search_enabled=False)
        assert result["sources"] == []
        assert CALLS["chat"] == 1

    def test_stock_price_direct_quote(self, service, monkeypatch):
        """股价问题(不带代码的中文名) → 行情数字直接进 system, sources 含腾讯行情"""
        class Resp:
            text = ('v_usBABA="200~阿里巴巴~BABA.N~113.24~111.81~112.37~7182522~0~0~'
                    '113.01~100~0~0~0~0~0~0~0~0~113.18~100~0~0~0~0~0~0~0~0~~'
                    '2026-09-04 16:04:38~1.43~1.28~113.41~111.97~USD~7182522~'
                    + "810867596~0.29~25.89~~17.76~1:8~1.29~2765.24284~2814.72018~"
                    + "Alibaba Group Holding Ltd~" + "~".join(["0"] * 30) + '";')
            encoding = "gbk"
        import core.stock as stock_mod
        monkeypatch.setattr(stock_mod.requests, "get", lambda *a, **kw: Resp())

        uid = 5112
        sid = self._session(service, uid)
        result = service.process_message(
            user_id=uid, session_id=sid, content="阿里巴巴股价多少",
            memory_enabled=False, search_enabled=True)
        system = next(m["content"] for m in LAST_CHAT_PAYLOADS[-1]["messages"]
                      if m["role"] == "system")
        assert "113.24" in system
        assert "实时行情" in system
        assert any(s["source"] == "tencent-quote" for s in result["sources"])

    def test_stock_route_matches_search_tool(self):
        """"股价"类查询路由到 search 工具（不再漏判为闲聊）"""
        from core.chat_router import chat_router
        assert chat_router.route("阿里巴巴股价多少")["tool"] == "search"
        assert chat_router.route("英伟达今天涨了还是跌了")["tool"] == "search"

    def test_real_tokens_used(self, service):
        """eval_count 真实值写入返回与 Message.tokens_used"""
        uid = 5106
        sid = self._session(service, uid)
        result = service.process_message(user_id=uid, session_id=sid, content="你好",
                                         memory_enabled=False, search_enabled=False)
        assert result["tokens_used"] == 8  # fakes 固定 eval_count=8

    def test_empty_response_raises_not_saves(self, service, monkeypatch):
        """LLM 返回空 → 抛 RuntimeError（路由层映射 503），不落消息"""
        from core import llm as llm_mod

        def fake_chat(*a, **kw):
            return {"message": {"content": ""}}
        monkeypatch.setattr(service.__class__, "build_context",
                            lambda *a, **kw: {"system_prompt": "s", "history": [],
                                              "memory_context": [], "analysis_result": {},
                                              "sources": []})
        monkeypatch.setattr(llm_mod.ollama_service, "chat", fake_chat)
        uid = 5107
        sid = self._session(service, uid)
        with pytest.raises(RuntimeError):
            service.process_message(user_id=uid, session_id=sid, content="你好")


class TestSessionCRUD:
    def test_rename_persist(self, service):
        uid = 5108
        sid = int(service.create_session(user_id=uid)["session_id"])
        assert service.rename_session(sid, "新标题") is True
        from models.sql_models import ChatSession
        row = service.db.query(ChatSession).filter(ChatSession.id == sid).first()
        assert row.title == "新标题"

    def test_delete_soft_persist(self, service):
        uid = 5109
        sid = int(service.create_session(user_id=uid)["session_id"])
        assert service.delete_session(sid) is True
        from models.sql_models import ChatSession
        row = service.db.query(ChatSession).filter(ChatSession.id == sid).first()
        assert row.deleted_at is not None
        # 再删一次 → False
        assert service.delete_session(sid) is False

    def test_rename_missing_false(self, service):
        assert service.rename_session(999999, "x") is False


class TestSSEStreamEndpoint:
    def test_stream_frames_and_storage(self):
        """SSE 帧序列 meta → delta+ → done；消息落库 user+assistant"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        sid = client.post("/api/v1/chat/sessions").json()["data"]["session_id"]

        with client.stream("POST", "/api/v1/chat/stream", json={
                "session_id": sid, "content": "你好",
                "memory_context": False, "search_enabled": False}) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            frames = [json.loads(line[6:]) for line in resp.iter_lines()
                      if line.startswith("data: ")]

        types = [f["type"] for f in frames]
        assert types[0] == "meta"
        assert types[-1] == "done" and frames[-1].get("done")
        assert "delta" in types
        assert not any(t == "error" for t in types)
        full = "".join(f["content"] for f in frames if f["type"] == "delta")
        assert full

        msgs = client.get(f"/api/v1/chat/sessions/{sid}/messages").json()["data"]["messages"]
        roles = [m["role"] for m in msgs]
        assert roles == ["user", "assistant"]
        assert msgs[1]["content"] == full


class TestMessageAPI:
    def test_llm_down_returns_503(self, monkeypatch):
        """Ollama 空响应 → HTTP 503 且不落空 assistant 消息"""
        from fastapi.testclient import TestClient
        from app.main import app
        import services.chat_service as cs_mod

        def empty(*a, **kw):
            return {"message": {"content": ""}, "eval_count": 0}
        monkeypatch.setattr(cs_mod.ollama_service, "chat", empty)

        client = TestClient(app)
        sid = client.post("/api/v1/chat/sessions").json()["data"]["session_id"]
        resp = client.post("/api/v1/chat/messages", json={
            "session_id": sid, "content": "你好",
            "memory_context": False, "search_enabled": False})
        assert resp.status_code == 503

        msgs = client.get(f"/api/v1/chat/sessions/{sid}/messages").json()["data"]["messages"]
        assert all(m["content"] for m in msgs)
