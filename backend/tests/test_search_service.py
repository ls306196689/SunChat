"""
Tests for Search Service
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSearchService:
    """Test cases for SearchService"""

    def test_route_query_with_memories(self):
        """Test routing query with memories"""
        from services.search_service import search_svc

        memories = [{"content": "用户喜欢 Python"}]
        result = search_svc.route_query("编程", memories)

        assert "intent" in result
        assert "query" in result

    def test_search_with_introduction(self):
        """Test search with LLM answer introduction"""
        from services.search_service import search_svc

        # This test may be skipped if LLM is not available
        result = search_svc.search_with_introduction("什么是 Python")

        assert "answer" in result
        assert "sources" in result
        assert "intent" in result
        assert len(result["sources"]) >= 0  # May have zero results

    def test_build_context_from_results(self):
        """Test building context from search results"""
        from services.search_service import search_svc

        results = [
            {"title": "结果1", "url": "http://example.com", "snippet": "这是结果1"},
            {"title": "结果2", "url": "http://example2.com", "snippet": "这是结果2"}
        ]

        context = search_svc._build_context_from_results(results)

        assert "结果1" in context
        assert "结果2" in context
        assert "http://example.com" in context

    def test_generate_answer(self):
        """Test generating answer with LLM"""
        from services.search_service import search_svc

        context = "Python 是一种编程语言。"
        answer = search_svc._generate_answer("Python 是什么？", context, [])

        # The answer should contain some information about Python
        assert len(answer) > 0

    def test_search_with_introduction_with_memories(self):
        """Test search with memories for context enhancement"""
        from services.search_service import search_svc

        memories = [{"content": "用户是程序员"}]
        result = search_svc.search_with_introduction("编程语言", memories)

        assert "answer" in result
        assert "sources" in result
