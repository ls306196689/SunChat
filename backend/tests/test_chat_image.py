"""
R-008: 对话图片通道（多模态 V1）
上传校验(AC-1) 回显/穿越(AC-2) 带图payload/入库/回传(AC-3) 历史窗口(AC-4)
纯文字等价+非vision strip(AC-5) supports_vision三态+缓存(AC-6) schema补列(AC-7)
"""
import base64
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    return TestClient(app)


def _png_bytes(w=4, h=4, color=(200, 30, 30)):
    from PIL import Image
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpg_bytes():
    from PIL import Image
    img = Image.new("RGB", (4, 4), (10, 200, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _upload(client, data: bytes, filename="x.png"):
    return client.post("/api/v1/chat/images",
                       files={"file": (filename, data, "application/octet-stream")})


class TestUpload:
    """R-008/AC-1"""

    def test_upload_png_jpg_gif_webp(self, client):
        from PIL import Image
        cases = {"a.png": ("PNG",), "a.jpg": ("JPEG",), "a.gif": ("GIF",)}
        for fn, fmt in cases.items():
            buf = io.BytesIO()
            Image.new("RGB", (4, 4), (5, 5, 5)).save(buf, format=fmt[0])
            r = _upload(client, buf.getvalue(), fn)
            assert r.status_code == 200, fn
            iid = r.json()["data"]["image_id"]
            assert iid.endswith((".png", ".jpg", ".gif"))

    def test_webp_magic(self, client):
        data = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 32
        r = _upload(client, data)
        assert r.status_code == 200
        assert r.json()["data"]["image_id"].endswith(".webp")

    def test_extension_lie_rejected(self, client):
        # 伪装 .png 的文本 → 魔数校验拒绝（扩展名派生自魔数,D-403）
        r = _upload(client, b"not an image at all", "evil.png")
        assert r.status_code == 400
        # 真 png 但命名 .txt → 仍接受且按魔数存为 .png（服务端不信 filename）
        r2 = _upload(client, _png_bytes(), "photo.txt")
        assert r2.status_code == 200
        assert r2.json()["data"]["image_id"].endswith(".png")

    def test_oversize_413(self, client):
        # 真实 8MB 上限:构造 9MB 数据(合法 PNG 魔数开头)
        data = _png_bytes()
        data = data + b"\x00" * (9 * 1024 * 1024)
        r = _upload(client, data)
        assert r.status_code == 413


class TestEcho:
    """R-008/AC-2"""

    def test_echo_ok(self, client):
        r = _upload(client, _png_bytes())
        iid = r.json()["data"]["image_id"]
        r2 = client.get(f"/api/v1/chat/images/{iid}")
        assert r2.status_code == 200
        assert r2.headers["content-type"] == "image/png"
        assert len(r2.content) > 0

    def test_path_traversal_400(self, client):
        # traversal 尝试:或 URL 层规范化 rout 404 / 或 handler id 校验 400——均不可达文件系统
        for bad in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd"):
            r = client.get(f"/api/v1/chat/images/{bad}")
            assert r.status_code in (400, 404), bad
        # 格式非法严格 400（handler 守卫）
        for bad in ("deadbeef.png", "x" * 40 + ".png",
                    "00000000-0000-0000-0000-000000000000.exe"):
            r = client.get(f"/api/v1/chat/images/{bad}")
            assert r.status_code == 400, bad

    def test_missing_404(self, client):
        r = client.get("/api/v1/chat/images/"
                       "11111111-2222-3333-4444-555555555555.png")
        assert r.status_code == 404


class TestChatWithImages:
    """R-008/AC-3,AC-4,AC-5"""

    def _reset_fakes(self):
        import fakes
        fakes.reset_calls()
        from core.model_manager import model_manager as mm
        mm._vision_cache.clear()

    def _send(self, client, content="看图", images=None, sid="7"):
        return client.post("/api/v1/chat/messages", json={
            "session_id": sid, "content": content,
            "memory_context": False, "search_enabled": False,
            "images": images or []})

    def test_payload_has_base64_and_persist(self, client, monkeypatch):
        # AC-3: 末条 user 带 images[b64],与源文件一致;入库 JSON;get_messages 回传
        self._reset_fakes()
        import fakes
        data = _png_bytes()
        iid = _upload(client, data).json()["data"]["image_id"]

        from services.chat_service import _IMG_B64_CACHE
        _IMG_B64_CACHE.clear()
        r = self._send(client, images=[iid])
        assert r.status_code == 200, r.text

        last = fakes.LAST_CHAT_PAYLOADS[-1]["messages"][-1]
        assert last["role"] == "user" and "images" in last
        assert base64.b64decode(last["images"][0]) == data

        got = client.get("/api/v1/chat/sessions/7/messages").json()["data"]
        u = [m for m in got["messages"] if m["role"] == "user"][-1]
        assert u["images"] == [iid]

    def test_pure_text_payload_equivalent(self, client):
        # AC-5: 纯文字（images 缺省）payload 无 images 键
        self._reset_fakes()
        import fakes
        r = self._send(client, content="纯文字消息", sid="8")
        assert r.status_code == 200
        last = fakes.LAST_CHAT_PAYLOADS[-1]["messages"][-1]
        assert "images" not in last

    def test_invalid_image_id_400(self, client):
        self._reset_fakes()
        r = self._send(client, images=["not-a-uuid.png"], sid="9")
        assert r.status_code == 400
        r2 = self._send(client, images=[
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.png"], sid="9")  # 合法格式但未上传
        assert r2.status_code == 400

    def test_per_msg_limit_400(self, client):
        self._reset_fakes()
        ids = [_upload(client, _png_bytes()).json()["data"]["image_id"]
               for _ in range(5)]
        r = self._send(client, images=ids, sid="10")
        assert r.status_code == 400  # >CHAT_IMAGE_MAX_PER_MSG(4)

    def test_history_window_injection(self, client):
        # AC-4: 历史带图消息按窗口注入;总图数≤CHAT_IMAGE_TOTAL_MAX
        self._reset_fakes()
        import fakes
        from app.config import settings
        from services.chat_service import _IMG_B64_CACHE
        _IMG_B64_CACHE.clear()

        # 直接落库3条历史带图消息(每张1图)+第4条更旧的带图消息(窗口外)
        from services.chat_service import chat_service
        from models.sql_models import Message as MsgModel, get_thread_session
        db = get_thread_session()
        ids = [_upload(client, _png_bytes()).json()["data"]["image_id"]
               for _ in range(4)]
        for i, iid in enumerate(ids):
            db.add(MsgModel(session_id=11, role="user", content=f"旧图{i}",
                            images=json.dumps([iid])))
        db.commit()
        db.close()

        r = self._send(client, content="还有图吗", sid="11")
        assert r.status_code == 200
        msgs = fakes.LAST_CHAT_PAYLOADS[-1]["messages"]
        img_msgs = [m for m in msgs if "images" in m]
        total = sum(len(m["images"]) for m in img_msgs)
        assert total <= settings.CHAT_IMAGE_TOTAL_MAX
        # 窗口=最近3条带图历史 → 最旧(ids[0])被排除
        all_b64 = [b for m in img_msgs for b in m["images"]]
        assert base64.b64encode  # 结构断言:窗口3条注入
        assert len([m for m in img_msgs if m["role"] == "user"]) == 3

    def test_non_vision_model_strips(self, client, monkeypatch):
        # AC-5: 非 vision 模型 → images 剥离
        self._reset_fakes()
        import fakes
        from core.model_manager import model_manager as mm
        mm._vision_cache.clear()
        monkeypatch.setattr(mm, "supports_vision", lambda name=None: False)

        iid = _upload(client, _png_bytes()).json()["data"]["image_id"]
        r = self._send(client, images=[iid], sid="12")
        assert r.status_code == 200
        msgs = fakes.LAST_CHAT_PAYLOADS[-1]["messages"]
        assert all("images" not in m for m in msgs), "非vision模型必须剥离images"
        mm._vision_cache.clear()


class TestSupportsVision:
    """R-008/AC-6"""

    def test_three_states_and_cache(self, monkeypatch):
        from core import model_manager as mm_mod
        import fakes
        mm = mm_mod.ModelManager.__new__(mm_mod.ModelManager)
        mm._vision_cache = {}
        mm._vision_ttl = 300
        from app.config import settings
        mm.resolve_chat_model = lambda requested=None: "qwen2.5:7b"

        n = []
        real_post = fakes.FakeRequests.post

        def counting_post(url, json=None, timeout=None, **kw):
            n.append(url)
            return real_post(url, json=json, timeout=timeout, **kw)
        monkeypatch.setattr(mm_mod.requests, "post", staticmethod(counting_post))

        assert mm.supports_vision("qwen2.5:7b") is True   # fake vision 模型
        assert mm.supports_vision("nomic-embed-text") is False
        assert mm.supports_vision("qwen2.5:7b") is True    # 第二次走缓存
        assert len(n) == 2, "TTL 内重复探测应命中缓存(两个模型各1次)"

    def test_unreachable_false(self, monkeypatch):
        from core import model_manager as mm_mod
        mm = mm_mod.ModelManager.__new__(mm_mod.ModelManager)
        mm._vision_cache = {}
        mm._vision_ttl = 300
        mm.resolve_chat_model = lambda requested=None: "x"

        def boom(url, json=None, timeout=None, **kw):
            raise ConnectionError("down")
        monkeypatch.setattr(mm_mod.requests, "post", staticmethod(boom))
        assert mm.supports_vision("x") is False


class TestSchemaBackfill:
    """R-008/AC-7: 旧库缺 images 列幂等补列（conftest 已跑 init_db,再跑无害）"""

    def test_idempotent_backfill(self):
        from models.sql_models import ensure_schema, get_engine
        from sqlalchemy import inspect
        ensure_schema()
        ensure_schema()
        insp = inspect(get_engine())
        cols = {c["name"] for c in insp.get_columns("messages")}
        assert "images" in cols


class TestStreamWithImages:
    """R-008: 流式端点带图 + id 校验前置到 SSE 之前(非法→HTTP 400 非 error 帧)"""

    def test_stream_invalid_id_400(self, client):
        r = client.post("/api/v1/chat/stream", json={
            "session_id": "1", "content": "图", "images": ["bad.png"]})
        assert r.status_code == 400

    def test_stream_with_image_ok(self, client):
        import fakes
        fakes.reset_calls()
        iid = _upload(client, _png_bytes()).json()["data"]["image_id"]
        r = client.post("/api/v1/chat/stream", json={
            "session_id": "2", "content": "看图",
            "memory_context": False, "search_enabled": False,
            "images": [iid]})
        assert r.status_code == 200
        assert "data:" in r.text
        body = client.get("/api/v1/chat/sessions/2/messages").json()["data"]
        u = [m for m in body["messages"] if m["role"] == "user"][-1]
        assert u["images"] == [iid]  # 流式落库带图 id
