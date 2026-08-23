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

    # Mock environment variables
    with mock.patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./data/test_sunchat.db",
        "CHROMA_PERSIST_DIR": "./data/test_chroma",
        "LLM_API_URL": "http://localhost:11434",
        "EMBEDDING_API_URL": "http://localhost:11434",
        "LLM_MODEL": "qwen2.5:7b",
        "EMBEDDING_MODEL": "nomic-embed-text"
    }):
        # Reload config to pick up new environment variables
        import importlib
        import app.config
        importlib.reload(app.config)

        # Import after environment is set
        from models.sql_models import init_db

        # Initialize test database
        init_db()

        yield

    # Cleanup after all tests
    if os.path.exists("./data/test_sunchat.db"):
        os.remove("./data/test_sunchat.db")

    if os.path.exists("./data/test_chroma"):
        shutil.rmtree("./data/test_chroma")


@pytest.fixture
def memory_service():
    """Create a test memory service instance"""
    from services.memory_service import MemoryService
    service = MemoryService()

    # Reset Chroma collection before test to ensure clean state
    service.chroma_client.reset()

    yield service

    # Cleanup - delete all test data
    from models.sql_models import Memory, Emotion
    service.db.query(Memory).delete()
    service.db.query(Emotion).delete()
    service.db.commit()
    service.chroma_client.reset()
    service.db.close()


@pytest.fixture
def client():
    """Create test client"""
    from fastapi.testclient import TestClient
    from app.main import app

    # Set environment before importing app
    os.environ["DATABASE_URL"] = "sqlite:///./data/test_sunchat.db"
    os.environ["CHROMA_PERSIST_DIR"] = "./data/test_chroma"

    # Re-import to reload with new config
    import importlib
    import app.config
    importlib.reload(app.config)

    # Re-initialize database
    from models.sql_models import init_db
    init_db()

    return TestClient(app)
