"""
Tests for Knowledge Service
"""
import pytest
import os
import sys
import shutil
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.knowledge_service import KnowledgeService, ChromaKnowledgeClient
from models.sql_models import init_db, get_db, reset_engine
from core.document_parser import document_parser


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


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
def knowledge_service():
    """Create a test knowledge service instance"""
    service = KnowledgeService()
    service.db = next(get_db())

    yield service

    # Cleanup
    service.db.close()
    service.chroma_client.reset()


class TestKnowledgeService:
    """Test cases for KnowledgeService"""

    def test_upload_file(self, knowledge_service):
        """Test uploading a file"""
        user_id = 2001
        result = knowledge_service.upload_file(
            user_id=user_id,
            filename="test.txt",
            original_name="测试文档.txt",
            file_type="txt",
            file_size=1024
        )

        assert result is not None
        assert "file_id" in result
        assert result["status"] == "uploading"

    def test_process_txt_file(self, knowledge_service, temp_dir):
        """Test processing a TXT file"""
        # Create a test TXT file
        txt_file = os.path.join(temp_dir, "test.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("# 标题\n")
            f.write("这是第一段内容，包含一些文本用于测试。\n")
            f.write("这是第二段内容，包含更多文本。\n\n")
            f.write("这是第三段内容。\n")

        # Upload file
        user_id = 2002
        upload_result = knowledge_service.upload_file(
            user_id=user_id,
            filename="test.txt",
            original_name="测试文档.txt",
            file_type="txt",
            file_size=os.path.getsize(txt_file)
        )

        # Process file
        result = knowledge_service.process_file(
            file_id=upload_result["file_id"],
            file_path=txt_file,
            file_type="txt"
        )

        assert result["status"] == "ready"
        assert "chunk_count" in result
        assert result["chunk_count"] > 0

    def test_process_md_file(self, knowledge_service, temp_dir):
        """Test processing a Markdown file"""
        # Create a test MD file
        md_file = os.path.join(temp_dir, "test.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# 标题1\n")
            f.write("这是第一段内容。\n")
            f.write("\n")
            f.write("## 标题2\n")
            f.write("这是第二段内容。\n")

        # Upload file
        user_id = 2003
        upload_result = knowledge_service.upload_file(
            user_id=user_id,
            filename="test.md",
            original_name="测试文档.md",
            file_type="md",
            file_size=os.path.getsize(md_file)
        )

        # Process file
        result = knowledge_service.process_file(
            file_id=upload_result["file_id"],
            file_path=md_file,
            file_type="md"
        )

        assert result["status"] == "ready"
        assert "chunk_count" in result

    def test_get_files(self, knowledge_service):
        """Test getting file list"""
        user_id = 2004

        # Upload some files
        knowledge_service.upload_file(
            user_id=user_id,
            filename="file1.txt",
            original_name="文件1.txt",
            file_type="txt",
            file_size=100
        )

        knowledge_service.upload_file(
            user_id=user_id,
            filename="file2.md",
            original_name="文件2.md",
            file_type="md",
            file_size=200
        )

        # Get files
        files = knowledge_service.get_files(user_id=user_id)

        assert len(files) >= 2
        # Check that both files are in the list
        filenames = [f["filename"] for f in files]
        assert "file1.txt" in filenames
        assert "file2.md" in filenames
        # Check status
        assert files[0]["status"] == "uploading"

    def test_delete_file(self, knowledge_service):
        """Test deleting a file"""
        user_id = 2005

        # Upload file
        upload_result = knowledge_service.upload_file(
            user_id=user_id,
            filename="to_delete.txt",
            original_name="删除测试.txt",
            file_type="txt",
            file_size=100
        )

        # Delete file
        result = knowledge_service.delete_file(upload_result["file_id"])

        assert result is True

        # Verify deletion
        files = knowledge_service.get_files(user_id=user_id)
        assert all(f["filename"] != "to_delete.txt" for f in files)

    def test_search_knowledge(self, knowledge_service, temp_dir):
        """Test searching knowledge base"""
        # Create a test file
        txt_file = os.path.join(temp_dir, "knowledge_test.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("# Python 编程\n")
            f.write("Python 是一种编程语言。\n")
            f.write("Python 可以用于 Web 开发。\n")
            f.write("Python 也可以用于数据分析。\n")

        # Upload and process file
        user_id = 2006
        upload_result = knowledge_service.upload_file(
            user_id=user_id,
            filename="knowledge_test.txt",
            original_name="知识测试.txt",
            file_type="txt",
            file_size=os.path.getsize(txt_file)
        )

        process_result = knowledge_service.process_file(
            file_id=upload_result["file_id"],
            file_path=txt_file,
            file_type="txt"
        )

        # Search
        results = knowledge_service.search_knowledge(
            user_id=user_id,
            query="Python 可以用来做什么",
            top_k=3
        )

        assert len(results) > 0
        assert "content" in results[0]
        assert "similarity" in results[0]
        assert results[0]["similarity"] >= 0

    def test_qa(self, knowledge_service, temp_dir):
        """Test knowledge base QA"""
        # Create a test file
        txt_file = os.path.join(temp_dir, "qa_test.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("# 项目信息\n")
            f.write("SunChat 是一个个人 AI 助手。\n")
            f.write("SunChat 运行在本地。\n")
            f.write("SunChat 使用 LLM 进行对话。\n")

        # Upload and process file
        user_id = 2007
        upload_result = knowledge_service.upload_file(
            user_id=user_id,
            filename="qa_test.txt",
            original_name="QA测试.txt",
            file_type="txt",
            file_size=os.path.getsize(txt_file)
        )

        knowledge_service.process_file(
            file_id=upload_result["file_id"],
            file_path=txt_file,
            file_type="txt"
        )

        # QA
        result = knowledge_service.qa(
            file_ids=[upload_result["file_id"]],
            query="SunChat 是什么？"
        )

        assert "answer" in result
        assert "sources" in result
        assert len(result["sources"]) > 0


class TestChromaKnowledgeClient:
    """Test cases for ChromaKnowledgeClient"""

    def test_add_and_query_vectors(self):
        """Test adding and querying vectors"""
        client = ChromaKnowledgeClient(persist_directory="./data/test_knowledge_chroma")

        # Add vectors
        ids = ["doc1", "doc2", "doc3"]
        documents = ["Python 编程", "JavaScript 开发", "Java 后端"]
        embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ]
        metadatas = [
            {"file_id": 1},
            {"file_id": 2},
            {"file_id": 3}
        ]

        client.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

        # Query
        results = client.query(query_embeddings=[[0.1, 0.2, 0.3]], n_results=2)

        assert "ids" in results
        assert len(results["ids"][0]) <= 2

        # Cleanup
        if os.path.exists("./data/test_knowledge_chroma"):
            shutil.rmtree("./data/test_knowledge_chroma")
