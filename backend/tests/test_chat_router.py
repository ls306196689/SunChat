"""
Tests for Chat Router
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestChatRouter:
    """Test cases for ChatRouter"""

    def test_route_to_memory(self):
        """Test routing to memory tool"""
        from core.chat_router import chat_router

        result = chat_router.route("我最喜欢的颜色是什么？")
        assert result["tool"] == "memory"
        assert result["confidence"] >= 0.8

    def test_route_to_knowledge(self):
        """Test routing to knowledge tool"""
        from core.chat_router import chat_router

        result = chat_router.route("这个文档里说了什么？")
        assert result["tool"] == "knowledge"
        assert result["confidence"] >= 0.8

    def test_route_to_search(self):
        """Test routing to search tool"""
        from core.chat_router import chat_router

        result = chat_router.route("今天的新闻是什么？")
        assert result["tool"] == "search"
        assert result["confidence"] >= 0.8

    def test_route_to_chat(self):
        """Test routing to chat tool (default)"""
        from core.chat_router import chat_router

        # 使用一个既不匹配记忆规则也不匹配搜索规则的查询
        result = chat_router.route("abcxyz测试对话123")
        assert result["tool"] == "chat"
        assert result["confidence"] >= 0.7

    def test_route_with_memories(self):
        """Test routing with memory context"""
        from core.chat_router import chat_router

        result = chat_router.route(
            "我之前提到过什么？",
            context={"memories": [{"content": "用户喜欢编程"}]}
        )
        assert "memories" in result

    def test_get_tools(self):
        """Test getting available tools"""
        from core.chat_router import chat_router

        tools = chat_router.get_tools()
        assert len(tools) == 4
        assert any(t["name"] == "memory" for t in tools)
        assert any(t["name"] == "knowledge" for t in tools)
        assert any(t["name"] == "search" for t in tools)
        assert any(t["name"] == "chat" for t in tools)

    def test_get_suggested_action(self):
        """Test getting suggested action"""
        from core.chat_router import chat_router

        result = chat_router._get_suggested_action("memory", "查询我的偏好", [])
        assert result["action"] == "search_memories"

        result = chat_router._get_suggested_action("chat", "你好", [])
        assert result["action"] == "chat"
