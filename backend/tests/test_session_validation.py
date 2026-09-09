"""
R-004: session_id 统一 400 校验 + 日志轮转测试
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestSessionIdValidation:
    """R-004/AC-1,AC-2: 非法 session_id → 400 且不落 service;合法 → 正常执行"""

    def _spy_service(self, monkeypatch):
        calls = []

        def fake_process_message(*a, **kw):
            calls.append(kw)
            return {"response": "ok", "memory_updates": [], "sources": [],
                    "tokens_used": 1}
        from services.chat_service import chat_service
        monkeypatch.setattr(chat_service, "process_message", fake_process_message)
        return calls

    def test_post_invalid_session_400(self, client, monkeypatch):
        calls = self._spy_service(monkeypatch)
        resp = client.post("/api/v1/chat/messages", json={
            "session_id": "abc", "content": "你好"})
        assert resp.status_code == 400
        assert "session_id" in resp.text
        assert not calls, "非法 id 不应进入 service"

    def test_post_empty_session_400(self, client, monkeypatch):
        calls = self._spy_service(monkeypatch)
        resp = client.post("/api/v1/chat/messages", json={
            "session_id": "", "content": "你好"})
        assert resp.status_code == 400
        assert not calls

    def test_post_valid_session_ok(self, client, monkeypatch):
        calls = self._spy_service(monkeypatch)
        resp = client.post("/api/v1/chat/messages", json={
            "session_id": "77", "content": "你好"})
        assert resp.status_code == 200
        assert calls and calls[0]["session_id"] == 77

    def test_stream_invalid_session_400(self, client, monkeypatch):
        calls = []
        from services.chat_service import chat_service

        def fake_build(*a, **kw):
            calls.append(1)
        monkeypatch.setattr(chat_service, "build_context", fake_build)
        resp = client.post("/api/v1/chat/stream", json={
            "session_id": "not-a-number", "content": "你好"})
        assert resp.status_code == 400
        assert not calls


class TestLoggerRotation:
    """R-004/AC-3: 超过 maxBytes 滚动备份;过期文件清理"""

    def test_rotating_handler_and_rotate(self, tmp_path, monkeypatch):
        import logging
        from logging.handlers import RotatingFileHandler
        from utils import logger as log_mod

        # 隔离 LOG_DIR/LOG_FILE 到 tmp,防清理逻辑误删真实历史日志
        monkeypatch.setattr(log_mod, "LOG_DIR", str(tmp_path))
        logger = logging.getLogger("rotation_test_unique")
        logger.handlers.clear()
        tmp_file = str(tmp_path / "sunchat_rottest.log")
        monkeypatch.setattr(log_mod, "LOG_FILE", tmp_file)
        logger = log_mod.get_logger("rotation_test_unique")
        try:
            handlers = [h for h in logger.handlers
                        if isinstance(h, RotatingFileHandler)]
            assert handlers, "应使用 RotatingFileHandler"
            h = handlers[0]
            assert h.maxBytes == log_mod.LOG_MAX_BYTES
            assert h.backupCount == log_mod.LOG_BACKUP_COUNT

            # 直接触发轮转
            h.maxBytes = 200
            for i in range(50):
                logger.info("x" * 60)
            assert os.path.exists(tmp_file + ".1"), "超容量后应产生 .1 备份"
        finally:
            for hh in list(logger.handlers):
                logger.removeHandler(hh)
                hh.close()

    def test_cleanup_removes_old_files(self, tmp_path, monkeypatch):
        import time
        from utils import logger as log_mod

        monkeypatch.setattr(log_mod, "LOG_DIR", str(tmp_path))
        old = tmp_path / "sunchat_20200101.log"
        old.write_text("old")
        old_time = time.time() - 40 * 86400
        os.utime(old, (old_time, old_time))
        keep = tmp_path / "sunchat_keepme.log"
        keep.write_text("keep")
        log_mod._cleanup_old_logs()
        assert not os.path.exists(old), "40 天前文件应被清理"
        assert os.path.exists(keep), "新文件不应被清理"
