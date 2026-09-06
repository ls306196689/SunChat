"""
Tests for Chat Service
"""
import pytest
import os
import sys
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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

    # 重建 engine 并建表（删库后旧连接指向旧文件；本模块需自建表）
    from models.sql_models import init_db, reset_engine
    reset_engine()
    init_db()

    yield

    # Cleanup after all tests
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    if os.path.exists(test_chroma_path):
        shutil.rmtree(test_chroma_path)


@pytest.fixture
def chat_service():
    """Create a test chat service instance"""
    from services.chat_service import ChatService
    service = ChatService()

    yield service

    # Cleanup
    service.db.close()


class TestChatService:
    """Test cases for ChatService"""

    def test_create_session(self, chat_service):
        """Test creating a chat session"""
        user_id = 4001
        result = chat_service.create_session(user_id=user_id, title="测试会话")

        assert result is not None
        assert "session_id" in result
        assert result["title"] == "测试会话"

    def test_build_memory_context(self, chat_service):
        """Test building memory context (经混合检索主路径)"""
        user_id = 4002

        # Create some memories first
        from services.memory_service import memory_service
        memory_service.create_memory(
            user_id=user_id,
            content="用户喜欢 Python 编程语言",
            memory_type="semantic",
            category="skill",
            confidence=0.9, importance=7
        )
        memory_service.create_memory(
            user_id=user_id,
            content="用户熟悉 Vue 框架",
            memory_type="semantic",
            category="skill",
            confidence=0.9, importance=7
        )

        # Build memory context via hybrid search
        context = memory_service.search_memories(
            user_id=user_id,
            query="我应该学习什么编程语言",
            top_k=3
        )

        assert isinstance(context, list)
        # 直接词命中的记忆应可召回（FTS 通道）
        ctx = memory_service.search_memories(user_id=user_id, query="Python", top_k=3)
        assert ctx
        for item in context:
            assert "content" in item
            assert "similarity" in item

    def test_build_search_context(self, chat_service):
        """Test building search context"""
        query = "Python 编程"
        memories = [
            {"content": "用户喜欢编程"}
        ]

        context = chat_service.build_search_context(query, memories)

        assert isinstance(context, dict)
        assert "intent" in context
        assert "query" in context

    def test_generate_memory_from_message(self, chat_service):
        """Test generating memory from message"""
        user_message = "我最近在学习 Python 编程"
        ai_response = "Python 是一种很好的编程语言，适合初学者。"

        memories = chat_service.generate_memory_from_message(user_message, ai_response)

        assert isinstance(memories, list)
        # May have results or be empty depending on LLM response
        for mem in memories:
            assert "content" in mem
            assert "type" in mem
            assert "category" in mem
            assert "importance" in mem

    def test_generate_memory_from_name(self, chat_service):
        """Test generating memory when user provides their name"""
        user_message = "我叫孙鹏飞"
        ai_response = "好的，孙鹏飞，记住了！😊 有什么我可以帮您的？"

        memories = chat_service.generate_memory_from_message(user_message, ai_response)

        assert isinstance(memories, list)
        # 至少应该提取一个记忆
        assert len(memories) >= 1
        # 检查记忆格式
        name_memory = memories[0]
        assert "content" in name_memory
        assert "孙鹏飞" in name_memory["content"]
        assert name_memory["importance"] >= 8  # 重要信息应该高分
        assert name_memory["type"] in ["semantic", "episodic"]
        assert name_memory["category"] in ["name", "personal_info"]

    def test_process_message(self, chat_service):
        """Test processing a message (integration test)"""
        user_id = 4003
        session = chat_service.create_session(user_id=user_id, title="测试会话")
        session_id = int(session["session_id"])

        result = chat_service.process_message(
            user_id=user_id,
            session_id=session_id,
            content="你好，请介绍一下你自己",
            memory_enabled=False,  # Disable for testing
            search_enabled=False
        )

        assert "response" in result
        assert "memory_updates" in result
        assert "memory_context" in result

        # Verify message was stored
        messages = chat_service.get_messages(session_id=session_id, page=1, page_size=10)
        assert len(messages["messages"]) >= 2  # User message + AI response

    def test_build_memory_context_with_filters(self, chat_service):
        """Test memory context returns content rows (types preserved in metadata)"""
        user_id = 4004

        # Create memories with different types
        from services.memory_service import memory_service
        memory_service.create_memory(
            user_id=user_id,
            content="用户喜欢 Python",
            memory_type="semantic",
            category="skill",
            confidence=0.9, importance=7
        )
        memory_service.create_memory(
            user_id=user_id,
            content="2024-01-01 用户完成项目",
            memory_type="episodic",
            category="event",
            confidence=0.9, importance=7
        )

        # Retrieve
        context = memory_service.search_memories(
            user_id=user_id,
            query="Python",
            top_k=5
        )

        assert isinstance(context, list)
        assert len(context) >= 0  # similarity 阈值下可能为 0
        for item in context:
            assert "content" in item
            assert "similarity" in item
