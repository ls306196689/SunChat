"""R-017 P4 pose-api 端点单测:200落库/拒析矩阵/503/日志(AC-2,AC-5,AC-6)
analyze_video 与 build_report monkeypatch(编排层验证;算法层见 test_pose_*)。
"""
import io
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _synth_avi(seconds=2.0, fps=15, size=48):
    import av
    buf = io.BytesIO()
    c = av.open(buf, "w", format="avi")
    st = c.add_stream("mjpeg", rate=fps)
    st.width = st.height = size
    st.pix_fmt = "yuvj420p"
    for i in range(int(seconds * fps)):
        arr = np.zeros((size, size, 3), dtype=np.uint8)
        arr[:, :, i % 3] = 200
        c.mux(st.encode(av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(format="yuvj420p")))
    c.mux(st.encode())
    c.close()
    return buf.getvalue()


def _mk_result():
    from core.pose import Cycle, PoseResult
    ts = [i / 15 for i in range(30)]
    lm = [(0.5, 0.5, 0, 0.9)] * 33
    lm[23] = (0.46, 0.5, 0, 0.9); lm[24] = (0.54, 0.5, 0, 0.9)
    lm[25] = (0.48, 0.68, 0, 0.9); lm[26] = (0.52, 0.68, 0, 0.9)
    lm[27] = (0.45, 0.85, 0, 0.9); lm[28] = (0.55, 0.83, 0, 0.9)
    lm[11] = (0.45, 0.3, 0, 0.9); lm[12] = (0.55, 0.3, 0, 0.9)
    lms = [list(lm) for _ in ts]
    cycles = [Cycle(0.2, 0.87, {"initial_contact_r": 0.2, "toe_off_r": 0.5,
                                "initial_contact_l": 0.53}, 113.0),
              Cycle(0.87, 1.53, {"initial_contact_r": 0.87, "toe_off_r": 1.2}, 113.0),
              Cycle(1.53, 1.9, {"initial_contact_r": 1.53}, 113.0)]
    return PoseResult(
        metrics={"cadence_spm": 172.0, "stance_swing_ratio": 0.8,
                 "knee_angle_at_contact_deg": 160.0, "knee_angle_at_toeoff_deg": 60.0,
                 "hip_rom_deg": 50.0, "pelvic_tilt_deg": 2.0, "asymmetry_pct": 5.0},
        quality={"mean_conf": 0.9, "body_ratio": 0.4, "cycles": 3, "score": 0.83},
        cycles=cycles, landmarks_seq=lms, sample_ts=ts, video_duration=2.0)


def _patch_ok(monkeypatch):
    import core.pose as cp
    monkeypatch.setattr(cp, "analyze_video", lambda data, **kw: _mk_result())


class TestPoseEndpoint:
    def _up(self, client, data, sid="21", name="r.avi"):
        return client.post("/api/v1/chat/video/pose",
                           files={"file": (name, data, "video/x-msvideo")},
                           data={"session_id": sid})

    def test_happy_200_db_echo_metrics(self, client, monkeypatch, caplog):
        """200 全键 + assistant 消息落库(extra 含指标) + 骨架帧回显 + evt=pose.analyze ok[AC-6]"""
        _patch_ok(monkeypatch)
        with caplog.at_level("INFO"):
            r = self._up(client, _synth_avi())
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        for k in ("report", "report_source", "frame_ids", "metrics", "quality", "message_id"):
            assert k in d
        assert d["metrics"]["cadence_spm"] == 172.0
        assert d["report_source"] in ("vl", "template")
        assert 1 <= len(d["frame_ids"]) <= 4
        fid = d["frame_ids"][0]
        r2 = client.get(f"/api/v1/chat/images/{fid}")
        assert r2.status_code == 200 and r2.content[:3] == b"\xff\xd8\xff"
        # 消息落库校验
        r3 = client.get(f"/api/v1/chat/sessions/21/messages")
        ms = r3.json()["data"]["messages"] if r3.status_code == 200 else []
        hit = [m for m in ms if m["id"] == d["message_id"]]
        assert hit and hit[0]["role"] == "assistant"
        imgs = hit[0]["images"]
        assert (json.loads(imgs) if isinstance(imgs, str) else imgs) == d["frame_ids"]
        assert "pose_metrics" in (hit[0].get("extra") or "")
        assert any("evt=pose.analyze" in l and "result=ok" in l for l in caplog.messages), "AC-6"

    def test_bad_magic_400(self, client):
        r = self._up(client, b"not-a-video" * 8)
        assert r.status_code == 400 and "不支持" in r.json()["detail"]

    def test_oversize_413(self, client, monkeypatch):
        from app.config import settings
        old = settings.VIDEO_MAX_MB
        settings.VIDEO_MAX_MB = 0
        try:
            r = self._up(client, _synth_avi(seconds=0.2))
            assert r.status_code == 413
        finally:
            settings.VIDEO_MAX_MB = old

    @pytest.mark.parametrize("reason", ["low_conf", "no_cycles", "body_too_small"])
    def test_quality_reject_400_with_hint(self, client, monkeypatch, reason, caplog):
        """AC-2:三类质量拒析 400 + 拍摄指引文案 + fail 日志(AC-6)"""
        import core.pose as cp

        def boom(data, **kw):
            raise cp.PoseQualityError(reason, "测试拒因")
        monkeypatch.setattr(cp, "analyze_video", boom)
        with caplog.at_level("ERROR"):
            r = self._up(client, _synth_avi())
        assert r.status_code == 400
        assert "拍摄要点" in r.json()["detail"]
        assert any(f"reason={reason}" in l for l in caplog.messages)

    def test_no_model_503(self, client, monkeypatch):
        import core.pose as cp

        def boom(data, **kw):
            raise FileNotFoundError("/x/pose_landmarker_lite.task")
        monkeypatch.setattr(cp, "analyze_video", boom)
        r = self._up(client, _synth_avi())
        assert r.status_code == 503 and "fetch_pose_model" in r.json()["detail"]

    def test_decoder_error_400_generic(self, client, monkeypatch):
        import core.pose as cp

        def boom(data, **kw):
            raise RuntimeError("broken stream")
        monkeypatch.setattr(cp, "analyze_video", boom)
        r = self._up(client, _synth_avi())
        assert r.status_code == 400

    def test_session_id_invalid_400(self, client, monkeypatch):
        _patch_ok(monkeypatch)
        r = self._up(client, _synth_avi(), sid="abc")
        assert r.status_code == 400


class TestSaveAssistantExtension:
    """CH-7:extra/images 默认参,既有位置参调用零改动"""

    def test_legacy_call_signature_still_works(self, client):
        from services.chat_service import chat_service
        m = chat_service.save_assistant_message(31, "hello", tokens_used=7)
        assert m.id and m.extra is None and m.images == "[]"

    def test_extra_column_migration_idempotent(self, client):
        from sqlalchemy import inspect, text
        from models.sql_models import get_engine, ensure_schema
        eng = get_engine()
        assert "extra" in {c["name"] for c in inspect(eng).get_columns("messages")}
        ensure_schema()  # 二次运行仍幂等
        assert "extra" in {c["name"] for c in inspect(eng).get_columns("messages")}
