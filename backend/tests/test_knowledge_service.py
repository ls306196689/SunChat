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

        # QA（传入属主 user_id，检索按用户隔离）
        result = knowledge_service.qa(
            file_ids=[upload_result["file_id"]],
            query="SunChat 是什么？",
            user_id=user_id
        )

        assert "answer" in result
        assert "sources" in result
        assert len(result["sources"]) > 0
        # 修复验证：来源内容取自 Chroma documents，必须非空
        assert result["sources"][0]["content_preview"].strip()
        assert "未找到相关文档" not in result["answer"]

    def test_search_knowledge_user_isolation(self, knowledge_service, temp_dir):
        """用户隔离：A 用户的文档不得被 B 用户检索到（where 过滤真正生效）"""
        txt_file = os.path.join(temp_dir, "secret.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("机密信息 只有属主可见 绝不外泄\n" * 5)

        owner = 2081
        other = 2082
        up = knowledge_service.upload_file(
            user_id=owner, filename="secret.txt", original_name="secret.txt",
            file_type="txt", file_size=os.path.getsize(txt_file)
        )
        knowledge_service.process_file(up["file_id"], txt_file, "txt")

        hits_owner = knowledge_service.search_knowledge(user_id=owner, query="机密信息", top_k=5)
        hits_other = knowledge_service.search_knowledge(user_id=other, query="机密信息", top_k=5)

        assert any("机密" in h["content"] for h in hits_owner)
        assert all("机密" not in h["content"] for h in hits_other)

    def test_delete_file_full_cleanup(self, knowledge_service, temp_dir):
        """删除文件：SQLite 分块 + Chroma 向量 + 物理文件都被清理"""
        txt_file = os.path.join(temp_dir, "cleanup.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("需要彻底清理的内容 段落一\n段落二\n段落三\n")

        storage = os.path.join(temp_dir, "stored_cleanup.txt")
        import shutil as _sh
        _sh.copyfile(txt_file, storage)

        up = knowledge_service.upload_file(
            user_id=2083, filename="cleanup.txt", original_name="cleanup.txt",
            file_type="txt", file_size=os.path.getsize(storage), storage_path=storage
        )
        knowledge_service.process_file(up["file_id"], storage, "txt")

        assert knowledge_service.delete_file(up["file_id"]) is True
        assert not os.path.exists(storage)
        from models.sql_models import KBChunk
        assert knowledge_service.db.query(KBChunk).filter(
            KBChunk.file_id == up["file_id"]).count() == 0
        # Chroma 中该文件向量已清空
        got = knowledge_service.chroma_client.get_stored_embeddings(
            where={"file_id": up["file_id"]})
        assert len(got.get("ids", [])) == 0

    def test_retry_resets_to_processing(self, knowledge_service, temp_dir):
        """重试：failed 文件重置为 processing 并返回落盘路径"""
        txt_file = os.path.join(temp_dir, "retry.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("重试内容 测试段落\n" * 4)

        up = knowledge_service.upload_file(
            user_id=2084, filename="retry.txt", original_name="retry.txt",
            file_type="txt", file_size=os.path.getsize(txt_file),
            storage_path=txt_file
        )
        # 人为制造失败状态
        from models.sql_models import KBFile
        row = knowledge_service.db.query(KBFile).filter(KBFile.id == up["file_id"]).first()
        row.status = "failed"
        row.error_message = "boom"
        knowledge_service.db.commit()

        result = knowledge_service.retry_process_file(up["file_id"])
        assert result["status"] == "processing"
        assert result["storage_path"] == txt_file
        assert result["file_type"] == "txt"


class TestKnowledgeUploadAPI:
    """上传路由：校验 + 落盘 + 后台处理"""

    def test_upload_rejects_bad_type(self, client):
        resp = client.post(
            "/api/v1/kb/upload",
            files={"file": ("evil.exe", b"MZ\x00\x00", "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_upload_persists_and_processes(self, client):
        content = "落盘测试正文 段落A\n段落B\n段落C\n".encode("utf-8")
        resp = client.post(
            "/api/v1/kb/upload",
            files={"file": ("persist_test.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["file_id"]

        # BackgroundTasks 在 TestClient 响应后同步执行完毕 → 应变为 ready
        listed = client.get("/api/v1/kb/files").json()["data"]["files"]
        mine = [f for f in listed if f["id"] == data["file_id"]]
        assert mine and mine[0]["status"] == "ready"

        # 删除走真实清理
        resp_del = client.delete(f"/api/v1/kb/files/{data['file_id']}")
        assert resp_del.status_code == 200
        listed = client.get("/api/v1/kb/files").json()["data"]["files"]
        assert all(f["id"] != data["file_id"] for f in listed)

    def test_delete_missing_file_404(self, client):
        resp = client.delete("/api/v1/kb/files/999999")
        assert resp.status_code == 404



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
