"""
Pytest configuration for backend tests
"""
import pytest
import os
import sys
import shutil
from unittest import mock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session", autouse=True)
def offline_network_guard():
    """全局离线守卫:LLM/嵌入/模型列表/搜索全部走 fakes,测试不触网。"""
    import fakes
    patchers = fakes.install()
    yield
    fakes.uninstall(patchers)


@pytest.fixture(scope="session", autouse=True)
def global_test_env_isolation():
    """会话级环境隔离：钉死测试环境变量（相对 ./data），禁止打生产库。
    生产库防护另有 sql_models._guard_pytest_real_db 兜底。"""
    os.makedirs("./data", exist_ok=True)
    with mock.patch.dict(os.environ, {
        "LLM_API_URL": "http://localhost:11434",
        "EMBEDDING_API_URL": "http://localhost:11434",
        "LLM_MODEL": "qwen2.5:7b",
        "EMBEDDING_MODEL": "nomic-embed-text",
    }):
        yield


def _clear_chroma_cache():
    try:
        from chromadb.api.client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass


@pytest.fixture(scope="module", autouse=True)
def module_isolated_env(request):
    """每模块独立 DB + Chroma 目录。

    - sqlite 删库会让另一模块持有的连接 unlink → 'readonly/unable to open';
    - chromadb 按 path 全局缓存 system，跨模块删目录留下被 unlink 的陈旧句柄。
    故每模块各用一套文件，并在切换前后清 chroma system 缓存。
    该 autouse 早于模块内其它 fixture(含各自 init_db)，模块 fixture 无需再改环境变量。
    历史事故：模块级同名 setup fixture 遮蔽 conftest 同名 fixture 导致打穿生产库，
    因此本 fixture 专名 + sql_models 守卫 双保险。"""
    import importlib
    import app.config

    mod = request.node.name.replace(".py", "") or "default"
    chroma_path = f"./data/test_chroma_{mod}"
    db_path = f"./data/test_sunchat_{mod}.db"
    imgs_path = f"./data/test_chat_imgs_{mod}"  # R-008: 对话图片目录隔离

    _clear_chroma_cache()
    prev_db = os.environ.get("DATABASE_URL")
    prev_chroma_env = os.environ.get("CHROMA_PERSIST_DIR")
    prev_imgs_env = os.environ.get("CHAT_IMAGE_DIR")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["CHROMA_PERSIST_DIR"] = chroma_path
    os.environ["CHAT_IMAGE_DIR"] = imgs_path
    importlib.reload(app.config)

    for p in (chroma_path, db_path, imgs_path):
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    os.makedirs(chroma_path, exist_ok=True)

    from models.sql_models import reset_engine, init_db
    reset_engine()
    init_db()

    yield

    # 清缓存 + 复原环境（避免卸载 app 时持有已删文件）
    reset_engine()
    _clear_chroma_cache()
    if prev_db is not None:
        os.environ["DATABASE_URL"] = prev_db
    else:
        os.environ.pop("DATABASE_URL", None)
    if prev_chroma_env is not None:
        os.environ["CHROMA_PERSIST_DIR"] = prev_chroma_env
    else:
        os.environ.pop("CHROMA_PERSIST_DIR", None)
    if prev_imgs_env is not None:
        os.environ["CHAT_IMAGE_DIR"] = prev_imgs_env
    else:
        os.environ.pop("CHAT_IMAGE_DIR", None)
    importlib.reload(app.config)

    for p in (chroma_path, db_path, imgs_path):
        if os.path.isdir(p):
            try:
                shutil.rmtree(p)
            except OSError:
                pass
        elif os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


@pytest.fixture
def memory_service():
    """线程安全测试用 MemoryService，前后清空。"""
    from services.memory_service import MemoryService
    from models.sql_models import get_thread_session
    service = MemoryService()
    service.chroma_client.reset()
    yield service
    session = get_thread_session()
    from models.sql_models import Memory, Emotion
    session.query(Memory).delete()
    session.query(Emotion).delete()
    session.commit()
    service.chroma_client.reset()


@pytest.fixture
def client():
    """FastAPI TestClient（用当前模块已隔离好的 env）。"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
