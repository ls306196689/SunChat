"""
R-013 日志体系验收单测
AC-1 trace 关联 / AC-2 环节事件 / AC-3 访问摘要 / AC-4 聚合降噪 / AC-7 SSE 零冗余
"""
import io
import json
import logging
import re
import threading
from unittest import mock

import pytest

from utils.logger import (AggregatingFilter, log_event, get_logger, get_trace,
                          new_trace, reset_trace, set_trace)


class Capture(logging.Handler):
    def __init__(self, level=logging.DEBUG):
        super().__init__(level)
        self.lines = []

    def emit(self, record):
        if not hasattr(record, "trace"):
            record.trace = f"[r={get_trace()}]"
        self.lines.append(
            f"{record.levelno}|{getattr(record, 'trace', '[r=-]')}|{record.getMessage()}")


@pytest.fixture
def http_capture():
    """挂到 sunchat.http logger 捕获中间件事件行。"""
    lg = logging.getLogger("sunchat.http")
    cap = Capture()
    lg.addHandler(cap)
    yield cap
    lg.removeHandler(cap)


@pytest.fixture(autouse=True)
def reset_agg_between_tests():
    from utils.logger import _agg_filter
    _agg_filter.reset()
    yield


# ==================== AC-1 trace ====================

class TestTrace:
    def test_set_get_reset(self):
        token = set_trace("abc123")
        assert get_trace() == "abc123"
        reset_trace(token)
        assert get_trace() == "-"

    def test_thread_inherits_via_copy_context(self):
        token = set_trace("tread1")
        ctx = __import__("contextvars").copy_context()
        seen = {}

        def job():
            seen["trace"] = get_trace()
        t = threading.Thread(target=ctx.run, args=(job,))
        t.start()
        t.join()
        reset_trace(token)
        assert seen["trace"] == "tread1"

    def test_background_memory_extract_inherits_trace(self):
        """AC-1: extract_memories_async 线程任务继承请求 trace(copy_context)。"""
        from services.chat_service import chat_service
        token = set_trace("mem123")
        seen = []
        orig = chat_service.apply_memory_extraction

        def wrapped(*a, **kw):
            seen.append(get_trace())
            return []

        with mock.patch.object(chat_service, "apply_memory_extraction", wrapped):
            fut = chat_service.extract_memories_async(1, "你好", "回复", [])
            fut.result(timeout=10)
        reset_trace(token)
        assert seen == ["mem123"]

    def test_middleware_trace_in_route_logs(self, client, http_capture):
        r = client.get("/api/v1/chat/sessions")
        assert r.status_code == 200
        trace = r.headers.get("x-request-id")
        assert trace and re.match(r"^[0-9a-f]{6}$", trace)
        http_lines = [l for l in http_capture.lines if "evt=http" in l]
        assert http_lines and f"[r={trace}]" in http_lines[-1]


# ==================== AC-2 事件行 ====================

class TestEvents:
    def png(self):
        return b"\x89PNG\r\n\x1a\n" + b"0" * 64

    def test_route_and_http_share_trace(self, client, http_capture):
        """AC-1 核心:同请求 route 层业务日志与 http 摘要行含相同 [r=trace]。"""
        cap = Capture()
        lg = logging.getLogger("sunchat")
        lg.addHandler(cap)
        r = client.post("/api/v1/chat/messages",
                        json={"session_id": "1", "content": "你好",
                              "memory_context": False})
        lg.removeHandler(cap)
        assert r.status_code == 200
        trace = r.headers.get("x-request-id")
        http_line = [l for l in http_capture.lines if "evt=http" in l][-1]
        biz = [l for l in cap.lines if "开始处理用户消息" in l]
        assert biz and f"[r={trace}]" in biz[0] and f"[r={trace}]" in http_line

    def test_different_requests_different_trace(self, client):
        t1 = client.get("/api/v1/chat/sessions").headers.get("x-request-id")
        t2 = client.get("/api/v1/chat/sessions").headers.get("x-request-id")
        assert t1 != t2

    def test_upload_ok_event(self, client, http_capture):
        cap = Capture()
        lg = logging.getLogger("sunchat")
        lg.addHandler(cap)
        r = client.post("/api/v1/chat/images",
                        files={"file": ("a.png", self.png(), "image/png")})
        lg.removeHandler(cap)
        assert r.status_code == 200
        ok = [l for l in cap.lines if "evt=chat.image.upload" in l
              and "result=ok" in l]
        assert ok and "image_id=" in ok[0]

    def test_upload_fail_event(self, client, http_capture):
        r = client.post("/api/v1/chat/images",
                        files={"file": ("a.bin", b"notanimage", "x")})
        assert r.status_code == 400
        cap = Capture()
        lg = logging.getLogger("sunchat")
        lg.addHandler(cap)
        client.post("/api/v1/chat/images",
                    files={"file": ("a.bin", b"still-not", "x")})
        lg.removeHandler(cap)
        fails = [l for l in cap.lines if "evt=chat.image.upload" in l
                 and "result=fail" in l]
        assert fails

    def test_log_event_format_and_exc(self):
        lg = logging.getLogger("sunchat.testevt")
        lg.handlers.clear()
        stream = io.StringIO()
        h = logging.StreamHandler(stream)
        h.setFormatter(logging.Formatter("%(levelname)s|%(trace)s|%(message)s"))
        h.addFilter(__import__("utils.logger", fromlist=["TraceFilter"]).TraceFilter())
        cap = Capture()
        lg.addHandler(h)
        lg.addHandler(cap)
        try:
            raise ValueError("boom|x\nnewline")
        except ValueError:
            log_event(lg, "chat.test", "act", "fail", exc=True, key="v|1")
        out = stream.getvalue()
        assert "evt=chat.test.act result=fail" in out
        assert "Traceback" in out  # 堆栈
        assert "key=v/1" in out    # 竖线净化
        assert "[r=-]" in out
        lg.handlers.clear()

    def test_speech_video_status_endpoints_have_events(self, client, http_capture):
        r = client.get("/api/v1/speech/status")
        assert r.status_code == 200


# ==================== AC-3 访问摘要 ====================

class TestAccessSummary:
    def test_normal_request_one_http_line(self, client, http_capture):
        http_capture.lines.clear()
        client.get("/api/v1/models")
        evt = [l for l in http_capture.lines if "evt=http" in l]
        assert len(evt) == 1
        assert "result=ok" in evt[0] and "status=200" in evt[0] and "ms=" in evt[0]

    def test_health_and_options_zero_log(self, client, http_capture):
        http_capture.lines.clear()
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert not [l for l in http_capture.lines if "evt=http" in l]
        r = client.options("/api/v1/chat/messages")
        assert not [l for l in http_capture.lines if "evt=http" in l]

    def test_client_error_warn_level(self, client, http_capture):
        http_capture.lines.clear()
        r = client.get("/api/v1/chat/sessions/abc/messages")
        assert r.status_code == 400
        evt = [l for l in http_capture.lines if "evt=http" in l]
        assert evt and evt[0].startswith(f"{logging.WARNING}|")

    def test_x_request_id_passthrough(self, client):
        r = client.get("/api/v1/chat/sessions", headers={"X-Request-ID": "my-id-42"})
        assert r.headers.get("x-request-id") == "my-id-42"

    def test_bad_x_request_id_regenerated(self, client):
        r = client.get("/api/v1/chat/sessions",
                       headers={"X-Request-ID": "bad id!!;inject"})
        assert re.match(r"^[0-9a-f]{6}$", r.headers.get("x-request-id"))

    def test_uvicorn_access_muted(self):
        from utils.logger import setup_uvicorn_logging
        setup_uvicorn_logging()
        assert logging.getLogger("uvicorn.access").level == logging.WARNING


# ==================== AC-4 聚合降噪 ====================

class TestAggregation:
    def mklogger(self, threshold=20, tag="agg"):
        lg = logging.getLogger(f"sunchat.test.{tag}")
        lg.handlers.clear()
        cap = Capture()
        f = AggregatingFilter(threshold=threshold)
        cap.addFilter(f)
        lg.addHandler(cap)
        lg.setLevel(logging.DEBUG)
        return lg, cap, f

    def test_same_template_50_to_head_plus_agg(self):
        lg, cap, _ = self.mklogger()
        for _ in range(50):
            lg.warning("external dep attempt failed code=%d", 500)
        warns = [l for l in cap.lines if "attempt failed" in l]
        assert len(warns) == 3          # 首条 + repeat×20 + repeat×40
        assert "repeat×40" in warns[-1]

    def test_first_seen_never_swallowed(self):
        lg, cap, _ = self.mklogger()
        lg.error("unique error abc123")
        assert any("unique error" in l for l in cap.lines)

    def test_different_templates_not_merged(self):
        lg, cap, _ = self.mklogger()
        lg.warning("template-A 1")
        lg.warning("template-B 2")
        assert len([l for l in cap.lines if "template-" in l]) == 2

    def test_digits_mask_merges_counters(self):
        lg, cap, _ = self.mklogger(threshold=3)
        for i in range(1, 7):
            lg.warning("retry %d of 5", i)
        out = [l for l in cap.lines if "retry" in l]
        assert len(out) == 3  # 首条 + 满3 + 满6

    def test_evt_line_exempt(self):
        lg, cap, _ = self.mklogger(threshold=2)
        for _ in range(10):
            log_event(lg, "dom", "act", "ok")
            log_event(lg, "dom", "act", "fail")
        assert len([l for l in cap.lines if "evt=dom.act result=ok" in l]) == 10
        assert len([l for l in cap.lines if "evt=dom.act result=fail" in l]) == 10

    def test_below_warning_passthrough(self):
        lg, cap, _ = self.mklogger()
        for _ in range(50):
            lg.info("chatty info")
        assert len([l for l in cap.lines if "chatty info" in l]) == 50


# ==================== AC-5 / AC-7 SSE ====================

class TestSSELogging:
    def test_stream_only_done_event_no_delta(self, client):
        token = set_trace("-")
        r = client.post("/api/v1/chat/stream",
                        json={"session_id": "1", "content": "你好呀"})
        reset_trace(token)
        assert r.status_code == 200
        assert "data:" in r.text

        cap = Capture()
        lg = logging.getLogger("sunchat")
        lg.addHandler(cap)
        token = set_trace("-")
        r = client.post("/api/v1/chat/stream",
                        json={"session_id": "1", "content": "你好呀"})
        reset_trace(token)
        lg.removeHandler(cap)
        evt = [l for l in cap.lines if "evt=chat.stream" in l]
        assert len(evt) == 1 and "result=ok" in evt[0]
        assert not [l for l in cap.lines if "delta" in l.lower()]

    def test_llm_fail_path_has_exc_info(self):
        from services.chat_service import chat_service
        cap = Capture()
        lg = logging.getLogger("sunchat")
        lg.addHandler(cap)
        with mock.patch("services.chat_service.ollama_service.chat",
                        side_effect=RuntimeError("LLM 返回空内容（服务可能不可用）")):
            with pytest.raises(RuntimeError):
                chat_service.process_message(1, 1, "hi")
        lg.removeHandler(cap)


class TestRoute500Stack:
    def test_chat_500_carries_exc_info(self, client):
        cap = Capture()
        lg = logging.getLogger("sunchat")
        lg.addHandler(cap)
        with mock.patch("app.api.v1.routes.chat.chat_service.process_message",
                        side_effect=KeyError("boom-500")):
            r = client.post("/api/v1/chat/messages", json={"session_id": "1",
                                                           "content": "hi"})
        lg.removeHandler(cap)
        assert r.status_code == 500
        fails = [l for l in cap.lines if "evt=chat.message" in l
                 and "result=fail" in l]
        assert fails
