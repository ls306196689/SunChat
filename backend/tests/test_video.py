"""
R-010: 视频输入(抽帧复用 R-008 图片通道)
extract_frames(AC-1) 端点矩阵(AC-2,AC-3) 帧回显=chat image(AC-2) 413/400(AC-3)
"""
import io
import math
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _synth_avi(seconds=3.0, fps=10, size=48):
    """合成色彩翻转 avi(mjpeg),离线可控。"""
    import av
    import numpy as np
    buf = io.BytesIO()
    c = av.open(buf, "w", format="avi")
    st = c.add_stream("mjpeg", rate=fps)
    st.width = size
    st.height = size
    st.pix_fmt = "yuvj420p"
    for i in range(int(seconds * fps)):
        arr = np.zeros((size, size, 3), dtype=np.uint8)
        if i % 6 < 3:
            arr[:, :, 0] = 220
        else:
            arr[:, :, 2] = 220
        f = av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(format="yuvj420p")
        c.mux(st.encode(f))
    c.mux(st.encode())
    c.close()
    return buf.getvalue()


class TestExtractFrames:
    """R-010/AC-1"""

    def test_synthetic_avi_frames(self):
        from core.video import extract_frames
        data = _synth_avi(seconds=3.0)
        frames, duration = extract_frames(data, max_frames=4)
        assert 1 <= len(frames) <= 4
        for jpeg, ts in frames:
            assert jpeg[:3] == b"\xff\xd8\xff", "必须为 JPEG"
        tss = [ts for _, ts in frames]
        assert tss == sorted(tss), "时间戳递增"
        assert duration > 2.5

    def test_max_frames_respected(self):
        from core.video import extract_frames
        frames, _ = extract_frames(_synth_avi(seconds=5.0), max_frames=2)
        assert len(frames) <= 2

    def test_invalid_bytes_raise(self):
        from core.video import extract_frames
        with pytest.raises(ValueError):
            extract_frames(b"not a video", max_frames=2)


class TestFramesEndpoint:
    """R-010/AC-2,AC-3"""

    def _up(self, client, data, name="v.avi"):
        return client.post("/api/v1/chat/video/frames",
                           files={"file": (name, data, "application/octet-stream")})

    def test_frames_200_and_echo(self, client):
        r = self._up(client, _synth_avi())
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["count"] == len(d["frame_ids"]) >= 1
        assert d["duration"] > 0
        # 帧 = 普通 chat image,GET 回显 200 image/jpeg
        fid = d["frame_ids"][0]
        r2 = client.get(f"/api/v1/chat/images/{fid}")
        assert r2.status_code == 200
        assert r2.headers["content-type"] == "image/jpeg"
        assert r2.content[:3] == b"\xff\xd8\xff"

    def test_bad_magic_400(self, client):
        r = self._up(client, b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, name="x.png")
        assert r.status_code == 400
        r2 = self._up(client, b"%PDF-1.4 not video")
        assert r2.status_code == 400

    def test_corrupt_ftyp_400(self, client):
        # 合法魔数但垃圾内容 → av 打不开 → ValueError → 400
        fake = b"\x00\x00\x00\x20ftypmp42" + b"\x00" * 200
        r = self._up(client, fake, name="v.mp4")
        assert r.status_code == 400

    def test_oversize_413(self, client):
        from app.config import settings
        old = settings.VIDEO_MAX_MB
        settings.VIDEO_MAX_MB = 0
        try:
            r = self._up(client, _synth_avi(seconds=0.2))
            assert r.status_code == 413
        finally:
            settings.VIDEO_MAX_MB = old


class TestFramesAsChatImages:
    """R-010/AC-4: frame_ids 当 images 发送 → payload 带 base64(复用 R-008 全链)"""

    def test_send_frames_through_chat(self, client, monkeypatch):
        import fakes
        fakes.reset_calls()
        from core.model_manager import model_manager as mm
        mm._vision_cache.clear()
        from services.chat_service import _IMG_B64_CACHE
        _IMG_B64_CACHE.clear()

        r = client.post("/api/v1/chat/video/frames",
                        files={"file": ("v.avi", _synth_avi(seconds=1.0),
                                        "video/x-msvideo")})
        assert r.status_code == 200
        frame_ids = r.json()["data"]["frame_ids"]

        r2 = client.post("/api/v1/chat/messages", json={
            "session_id": "21", "content": "视频里有什么",
            "memory_context": False, "search_enabled": False,
            "images": frame_ids})
        assert r2.status_code == 200
        last = fakes.LAST_CHAT_PAYLOADS[-1]["messages"][-1]
        assert last.get("images") and len(last["images"]) == len(frame_ids)
        import base64
        assert base64.b64decode(last["images"][0])[:3] == b"\xff\xd8\xff"
        got = client.get("/api/v1/chat/sessions/21/messages").json()["data"]
        u = [m for m in got["messages"] if m["role"] == "user"][-1]
        assert u["images"] == frame_ids
