"""
Tests for Memory Service
"""
import pytest
import os
import sys
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.memory_service import MemoryService, ChromaClient
from models.sql_models import init_db, get_db, reset_engine, Memory, Emotion


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
        shutil.rmtree(test_chroma_path)

    # 重建 engine（删库后旧连接仍指向旧文件）
    reset_engine()

    # Initialize test database
    init_db()

    yield

    # Cleanup after all tests
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    if os.path.exists(test_chroma_path):
        shutil.rmtree(test_chroma_path)


@pytest.fixture
def memory_service():
    """Create a test memory service instance with fresh database connection"""
    # Use a unique user_id for each test to avoid conflicts
    from services.memory_service import memory_service as global_service

    # Reset Chroma collection for clean state
    global_service.chroma_client.reset()

    yield global_service

    # Cleanup - delete all test data
    global_service.db.query(Memory).delete()
    global_service.db.query(Emotion).delete()
    global_service.db.commit()
    global_service.chroma_client.reset()


class TestMemoryService:
    """Test cases for MemoryService"""

    def test_create_memory(self, memory_service):
        """Test creating a memory"""
        user_id = 3001  # Unique user ID for test isolation
        content = "测试记忆内容：用户喜欢编程"
        memory = memory_service.create_memory(
            user_id=user_id,
            content=content,
            memory_type="semantic",
            category="preference",
            tags=["test", "coding"]
        )

        assert memory is not None
        assert memory["id"].startswith("mem_")
        assert memory["content"] == content
        assert "vector_id" in memory

        # Cleanup
        memory_service.delete_memory(memory["id"])

    def test_create_memory_with_different_types(self, memory_service):
        """Test creating memories of different types"""
        user_id = 3002  # Unique user ID for test isolation

        # Semantic memory
        semantic = memory_service.create_memory(
            user_id=user_id,
            content="用户喜欢 Python",
            memory_type="semantic",
            category="skill"
        )
        assert semantic["type"] == "semantic"
        memory_service.delete_memory(semantic["id"])

        # Episodic memory
        episodic = memory_service.create_memory(
            user_id=user_id,
            content="2024-01-01 用户完成了项目",
            memory_type="episodic",
            category="event"
        )
        assert episodic["type"] == "episodic"
        memory_service.delete_memory(episodic["id"])

    def test_search_memories_by_semantic(self, memory_service):
        """Test semantic search of memories"""
        user_id = 3003  # Unique user ID for test isolation

        # Create some memories
        m1 = memory_service.create_memory(
            user_id=user_id,
            content="用户喜欢 Python 编程",
            memory_type="semantic",
            category="skill"
        )
        m2 = memory_service.create_memory(
            user_id=user_id,
            content="用户熟悉 Vue 框架",
            memory_type="semantic",
            category="skill"
        )
        m3 = memory_service.create_memory(
            user_id=user_id,
            content="用户工作在科技公司",
            memory_type="semantic",
            category="work"
        )

        # Search
        results = memory_service.search_memories(
            user_id=user_id,
            query="用户擅长什么编程语言",
            top_k=5
        )

        assert len(results) > 0
        # Results should be sorted by similarity
        for i in range(len(results) - 1):
            assert results[i]["similarity"] >= results[i + 1]["similarity"]

        # Cleanup
        for m in [m1, m2, m3]:
            memory_service.delete_memory(m["id"])

    def test_search_memories_with_filters(self, memory_service):
        """Test searching memories with filters"""
        user_id = 3004  # Unique user ID for test isolation

        # Create memories with different categories
        m1 = memory_service.create_memory(
            user_id=user_id,
            content="Python 编程",
            memory_type="semantic",
            category="skill"
        )
        m2 = memory_service.create_memory(
            user_id=user_id,
            content="今天天气很好",
            memory_type="episodic",
            category="weather"
        )

        # Search - results should include semantic type
        all_results = memory_service.search_memories(
            user_id=user_id,
            query="编程",
            top_k=5
        )

        # At least one result should be semantic type
        semantic_results = [m for m in all_results if m.get("metadata", {}).get("type") == "semantic"]
        assert len(semantic_results) >= 1

        # Cleanup
        for m in [m1, m2]:
            memory_service.delete_memory(m["id"])

    def test_update_memory(self, memory_service):
        """Test updating a memory"""
        user_id = 3005  # Unique user ID for test isolation

        # Create a memory
        memory = memory_service.create_memory(
            user_id=user_id,
            content="原始内容",
            memory_type="semantic",
            category="test",
            importance=5
        )

        # Update
        from models.schemas import MemoryUpdate
        updates = MemoryUpdate(
            content="更新后的内容",
            importance=8,
            tags=["updated", "test"]
        )
        updated = memory_service.update_memory(memory["id"], updates)

        assert updated is not None
        assert updated["content"] == "更新后的内容"
        assert updated["importance"] == 8

        # Cleanup
        memory_service.delete_memory(memory["id"])

    def test_delete_memory(self, memory_service):
        """Test deleting a memory"""
        user_id = 3006  # Unique user ID for test isolation

        # Create a memory
        memory = memory_service.create_memory(
            user_id=user_id,
            content="将被删除的记忆",
            memory_type="semantic",
            category="test"
        )

        # Delete
        result = memory_service.delete_memory(memory["id"])
        assert result is True

        # Verify soft delete - memory should still exist in DB but is_active = False
        deleted_memory = memory_service.db.query(Memory).filter(Memory.id == memory["id"]).first()
        assert deleted_memory is not None
        assert deleted_memory.is_active == False

    def test_get_stats(self, memory_service):
        """Test getting memory statistics"""
        user_id = 3007  # Unique user ID for test isolation

        # Create some memories
        m1 = memory_service.create_memory(
            user_id=user_id,
            content="记忆 1",
            memory_type="semantic",
            category="skill"
        )
        m2 = memory_service.create_memory(
            user_id=user_id,
            content="记忆 2",
            memory_type="episodic",
            category="event"
        )
        m3 = memory_service.create_memory(
            user_id=user_id,
            content="记忆 3",
            memory_type="semantic",
            category="preference"
        )

        # Get stats
        stats = memory_service.get_stats(user_id=user_id)

        assert stats["total_count"] == 3
        assert "by_type" in stats
        assert "by_category" in stats
        assert "chroma_collection_size" in stats

        # Cleanup
        for m in [m1, m2, m3]:
            memory_service.delete_memory(m["id"])


class TestChromaClient:
    """Test cases for ChromaClient"""

    def test_chroma_client_initialization(self):
        """Test Chroma client initialization"""
        client = ChromaClient(persist_directory="./data/test_chroma_init")
        assert client._client is None  # Should be lazy-loaded

        # Access collection to trigger initialization
        collection = client._get_collection()
        assert collection is not None

        # Cleanup
        if os.path.exists("./data/test_chroma_init"):
            shutil.rmtree("./data/test_chroma_init")

    def test_add_and_query_vectors(self):
        """Test adding and querying vectors"""
        client = ChromaClient(persist_directory="./data/test_chroma_add_query")

        # Add vectors
        ids = ["vec1", "vec2", "vec3"]
        documents = ["Python 编程", "JavaScript 开发", "Java 后端"]
        embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ]
        metadatas = [
            {"category": "programming"},
            {"category": "programming"},
            {"category": "backend"}
        ]

        client.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

        # Query
        results = client.query(query_embeddings=[[0.1, 0.2, 0.3]], n_results=2)

        assert "ids" in results
        assert len(results["ids"][0]) <= 2

        # Cleanup
        if os.path.exists("./data/test_chroma_add_query"):
            shutil.rmtree("./data/test_chroma_add_query")
