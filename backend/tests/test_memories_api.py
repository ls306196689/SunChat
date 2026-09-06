"""
Tests for Memories API Endpoint
"""
import pytest
import os
import sys
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app


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


class TestMemoriesAPI:
    """Test cases for Memories API"""

    def test_create_memory_api(self, client):
        """Test creating a memory via API"""
        response = client.post(
            "/api/v1/memories",
            json={
                "content": "测试记忆：用户喜欢编程",
                "type": "semantic",
                "category": "preference",
                "tags": ["test", "coding"],
                "importance": 7
            }
        )

        # API returns 200 with code: 201 for success
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 201
        assert data["data"]["content"] == "测试记忆：用户喜欢编程"
        assert "id" in data["data"]

    def test_search_memories_api(self, client):
        """Test searching memories via API"""
        # First create a memory
        client.post(
            "/api/v1/memories",
            json={
                "content": "用户喜欢 Python 编程语言",
                "type": "semantic",
                "category": "skill",
                "importance": 8
            }
        )

        # Then search for it
        response = client.post(
            "/api/v1/memories/search",
            json={
                "query": "用户擅长什么编程语言",
                "top_k": 5
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "results" in data["data"]
        assert len(data["data"]["results"]) > 0
        # Check that similarity is in results
        assert "similarity" in data["data"]["results"][0]

    def test_list_memories_api(self, client):
        """Test listing memories via API（真实分页列表，非空壳）"""
        # 先确保至少有一条记忆
        client.post(
            "/api/v1/memories",
            json={"content": "列表测试记忆内容", "type": "semantic",
                  "category": "preference", "importance": 6},
        )
        response = client.get(
            "/api/v1/memories",
            params={"page": 1, "page_size": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "total" in data["data"]
        assert "memories" in data["data"]
        assert data["data"]["total"] >= 1
        assert any(m["content"] == "列表测试记忆内容" for m in data["data"]["memories"])

    def test_list_memories_filter(self, client):
        """列表支持 category 过滤"""
        client.post("/api/v1/memories", json={
            "content": "过滤测试技能项", "type": "semantic",
            "category": "skill", "importance": 5})
        resp = client.get("/api/v1/memories", params={"category": "skill"})
        assert resp.status_code == 200
        for m in resp.json()["data"]["memories"]:
            assert m["category"] == "skill"

    def test_get_memory_stats_api(self, client):
        """Test getting memory stats via API"""
        response = client.get("/api/v1/memories/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "total_count" in data["data"]
        assert "by_type" in data["data"]
