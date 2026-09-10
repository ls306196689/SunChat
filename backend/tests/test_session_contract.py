"""
R-005: session 契约收口 - GET 端点 400 + 分页限幅 + Agent 非法 id 400
覆盖 AC-1~AC-4(见 R-005/micro-req.md),根因见 R-005/analysis.md#A-1
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestGetMessagesContract:
    """R-005/AC-1,AC-2,AC-4: GET /chat/sessions/{id}/messages"""

    def _spy(self, monkeypatch):
        calls = []

        def fake_get_messages(**kw):
            calls.append(kw)
            return {"messages": [], "total": 0, "page": 1, "page_size": 20}
        from services.chat_service import chat_service
        monkeypatch.setattr(chat_service, "get_messages", fake_get_messages)
        return calls

    def test_get_invalid_session_400(self, client, monkeypatch):
        # AC-1: 非数字 → 400,R-004 契约对齐(原 500)
        calls = self._spy(monkeypatch)
        resp = client.get("/api/v1/chat/sessions/abc/messages")
        assert resp.status_code == 400
        assert "session_id" in resp.text
        assert not calls, "非法 id 不应进入 service"

    def test_get_valid_session_ok(self, client, monkeypatch):
        # AC-4: 合法数字回归不变
        calls = self._spy(monkeypatch)
        resp = client.get("/api/v1/chat/sessions/7/messages")
        assert resp.status_code == 200
        assert calls and calls[0]["session_id"] == 7

    def test_get_page_zero_422(self, client, monkeypatch):
        # AC-2/D-101: page=0 → 422(声明式 Query 校验),不再负 offset
        calls = self._spy(monkeypatch)
        resp = client.get("/api/v1/chat/sessions/1/messages?page=0")
        assert resp.status_code == 422
        assert not calls

    def test_get_page_size_over_limit_422(self, client, monkeypatch):
        # AC-2: page_size>100 → 422
        calls = self._spy(monkeypatch)
        resp = client.get("/api/v1/chat/sessions/1/messages?page_size=101")
        assert resp.status_code == 422
        assert not calls

    def test_get_pagination_bounds_ok(self, client, monkeypatch):
        # AC-4: 边界合法值 page=1/page_size=100 正常
        calls = self._spy(monkeypatch)
        resp = client.get("/api/v1/chat/sessions/1/messages?page=1&page_size=100")
        assert resp.status_code == 200
        assert calls and calls[0]["page_size"] == 100


class TestAgentSessionContract:
    """R-005/AC-3,AC-4: POST /chat/agent session_id 三分支"""

    def _spy(self, monkeypatch):
        from services.chat_service import chat_service
        from core.agent.agent import agent
        saved = []
        monkeypatch.setattr(chat_service, "get_recent_messages", lambda s: [])
        monkeypatch.setattr(chat_service, "save_user_message",
                            lambda s, m: saved.append(("user", s)))
        monkeypatch.setattr(chat_service, "save_assistant_message",
                            lambda s, m: saved.append(("asst", s)))
        monkeypatch.setattr(agent, "run", lambda *a, **k: {
            "content": "ok", "tool_trace": [], "iterations": 1, "mode": "text"})
        return saved

    def test_agent_nonempty_invalid_session_400(self, client, monkeypatch):
        # AC-3: 非空非法 → 400,禁止静默降级(原 200 不落库)
        saved = self._spy(monkeypatch)
        resp = client.post("/api/v1/chat/agent",
                           json={"content": "你好", "session_id": "abc"})
        assert resp.status_code == 400
        assert "session_id" in resp.text
        assert not saved

    def test_agent_empty_session_stateless_ok(self, client, monkeypatch):
        # AC-3/D-102: 空 id → 无会话模式保留(200 且不落库)
        saved = self._spy(monkeypatch)
        resp = client.post("/api/v1/chat/agent",
                           json={"content": "你好", "session_id": ""})
        assert resp.status_code == 200
        assert not saved

    def test_agent_absent_session_stateless_ok(self, client, monkeypatch):
        saved = self._spy(monkeypatch)
        resp = client.post("/api/v1/chat/agent", json={"content": "你好"})
        assert resp.status_code == 200
        assert not saved

    def test_agent_valid_session_persists(self, client, monkeypatch):
        # AC-4: 合法数字 → 落库回归不变
        saved = self._spy(monkeypatch)
        resp = client.post("/api/v1/chat/agent",
                           json={"content": "你好", "session_id": "9"})
        assert resp.status_code == 200
        assert saved == [("user", 9), ("asst", 9)]
