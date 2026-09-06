"""
Tests for Search History API
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from models.sql_models import init_db, SearchHistory, get_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """DB/Chroma 由 conftest 模块级隔离 fixture 建立; 此处仅确保表存在。"""
    from models.sql_models import init_db
    init_db()
    yield

@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestSearchHistoryAPI:
    """Test cases for Search History API"""

    def test_search_history_endpoint(self, client):
        """Test search history endpoint exists"""
        response = client.get("/api/v1/search/history")
        assert response.status_code == 200

    def test_save_search_history(self):
        """Test saving search history to database"""
        from services.search_service import search_svc

        # Simulate a search
        memories = [{"content": "用户喜欢编程"}]
        result = search_svc.search_with_introduction("Python 编程", memories)

        # Verify search was performed
        assert "answer" in result
        assert "sources" in result
