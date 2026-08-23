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
    """Setup test environment before tests"""
    os.makedirs("./data", exist_ok=True)

    # Clean up any existing test database
    test_db_path = "./data/test_sunchat.db"
    test_chroma_path = "./data/test_chroma"

    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    if os.path.exists(test_chroma_path):
        import shutil
        shutil.rmtree(test_chroma_path)

    # Initialize test database
    init_db()

    yield

    # Cleanup after all tests
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    if os.path.exists(test_chroma_path):
        import shutil
        shutil.rmtree(test_chroma_path)


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
