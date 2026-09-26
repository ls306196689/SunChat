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


def _synth_avi_rect(w=64, h=32, seconds=2.0, fps=15):
    """竖→横可辨的矩形视频(AC-5 用:转正与否落盘尺寸不同)。"""
    import av
    buf = io.BytesIO()
    c = av.open(buf, "w", format="avi")
    st = c.add_stream("mjpeg", rate=fps)
    st.width, st.height = w, h
    st.pix_fmt = "yuvj420p"
    for i in range(int(seconds * fps)):
        arr = np.zeros((h, w, 3), dtype=np.uint8)
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
                 "hip_rom_deg": 50.0, "pelvic_tilt_deg": 2.0, "asymmetry_pct": 5.0,
                 "pace": {"v_ms": 2.6, "kmh": 9.4, "min_per_km": 6.4,
                          "pace_str": "6:25", "stride_m": 0.91, "height_cm": 175.0},
                 "pace_reason": None},
        quality={"mean_conf": 0.9, "body_ratio": 0.4, "cycles": 3, "score": 0.83,
                 "fps_eff": 29.97, "fps_nominal": 30.0, "slo_factor": 1,
                 "vfr": False, "activity_span": 1.7},
        cycles=cycles, landmarks_seq=lms, sample_ts=ts, video_duration=2.0,
        crop_bbox=(0.25, 0.25, 0.75, 0.75))


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

    def test_v2_quality_passthrough_and_log_fields(self, client, monkeypatch, caplog):
        """v2:quality 透明度键透传 + pace 入 extra + 日志带 fps_eff/span/pace/crop 位。"""
        _patch_ok(monkeypatch)
        with caplog.at_level("INFO"):
            r = self._up(client, _synth_avi())
        assert r.status_code == 200, r.text
        q = r.json()["data"]["quality"]
        assert q["fps_eff"] == pytest.approx(29.97) and q["activity_span"] == 1.7
        assert r.json()["data"]["metrics"]["pace"]["pace_str"] == "6:25"
        line = [l for l in caplog.messages if "evt=pose.analyze" in l and "result=ok" in l][0]
        for frag in ("fps_eff=29.97", "span=1.7", "pace=y", "crop=y"):
            assert frag in line, f"日志缺 {frag}: {line}"

    def test_v2_skeleton_frame_is_cropped(self, client, monkeypatch):
        """AC-10:落盘骨架帧为裁剪版——crop=(0.25,0.25,0.75,0.75) → 尺寸=原帧 1/4×1/4。"""
        _patch_ok(monkeypatch)
        from PIL import Image
        import io as _io
        r = self._up(client, _synth_avi(size=48))
        assert r.status_code == 200, r.text
        fid = r.json()["data"]["frame_ids"][0]
        img = Image.open(_io.BytesIO(client.get(f"/api/v1/chat/images/{fid}").content))
        assert img.size == (24, 24), f"落盘应为裁剪版,实得 {img.size}"

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

    @pytest.mark.parametrize("reason", ["low_conf", "no_cycles", "body_too_small",
                                        "no_activity"])
    def test_quality_reject_400_with_hint(self, client, monkeypatch, reason, caplog):
        """AC-2+FR-9:质量拒析(含 v2 no_activity)400 + 拍摄指引文案 + fail 日志(AC-6)"""
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


class TestOrientPassthrough:
    """R-018 P4:端点同-k 取帧(AC-5)+ evt orient 字段(FR-5)。"""

    def _up(self, client, data, sid="41"):
        return client.post("/api/v1/chat/video/pose",
                           files={"file": ("r.avi", data, "video/x-msvideo")},
                           data={"session_id": sid})

    def _force_template(self, monkeypatch):
        """全局 fake LLM 支持视觉会走 VL 路(报告=固定假文案)→ 本类断言模板文案,
        固定走模板路(transparency 行在模板与 VL 上下文两路均有,模板侧可断)。"""
        from core.pose_report import template_report
        monkeypatch.setattr("core.pose_report.build_report",
                            lambda res, frames, **kw: (template_report(res), "template"))

    def test_frames_at_ts_rotates(self):
        """_frames_at_ts(rot=1) → 帧宽高互换;rot 缺省/越界 → 不转不抛。"""
        from app.api.v1.routes.chat import _frames_at_ts
        data = _synth_avi_rect(w=64, h=32)
        f0 = _frames_at_ts(data, [0.2])[0]
        f1 = _frames_at_ts(data, [0.2], 1)[0]
        assert f0 is not None and (f1.shape[0], f1.shape[1]) == (f0.shape[1], f0.shape[0])
        assert _frames_at_ts(data, [0.2])[0].shape == f0.shape
        assert _frames_at_ts(data, [0.2], 9)[0].shape == f0.shape  # 越界按 0

    def test_endpoint_passes_rot_k(self, client, monkeypatch):
        """AC-5:result.orient.rot_k=1 → 端点用 rot=1 取帧(横躺源视频落盘尺寸随之转正)。"""
        import core.pose as cp
        from app.api.v1.routes import chat as cr
        self._force_template(monkeypatch)
        seen = {}
        real = cr._frames_at_ts

        def spy(data, target_ts, rot=0):
            seen["rot"] = rot
            return real(data, target_ts, rot)
        monkeypatch.setattr(cr, "_frames_at_ts", spy)
        res = _mk_result()
        res.orient = {"orient": "90cw", "orient_conf": 1.0, "orient_samples": 9,
                      "orient_abstain": 0, "rot_k": 1}
        res.quality["orient"], res.quality["orient_conf"] = "90cw", 1.0
        monkeypatch.setattr(cp, "analyze_video", lambda data, **kw: res)
        r = self._up(client, _synth_avi_rect(w=64, h=32))
        assert r.status_code == 200, r.text
        assert seen.get("rot") == 1, "端点必须把 result.orient.rot_k 传给取帧(FR-4)"
        d = r.json()["data"]
        assert d["quality"]["orient"] == "90cw"
        assert "已按人体朝向转正" in d["report"] and "原为 90cw" in d["report"]
        from PIL import Image
        import io as _io
        fid = d["frame_ids"][0]
        img = Image.open(_io.BytesIO(client.get(f"/api/v1/chat/images/{fid}").content))
        # 同 k 取帧:64×32 源经 rot=1 → 32×64,crop(0.25..0.75) → 16×32(竖)
        # 负对照见 test_endpoint_default_no_orient_stays_unrotated(同夹具未传 rot → 32×16 横)
        assert img.size == (16, 32), f"骨架帧应在转正系内,实得 {img.size}" 

    def test_endpoint_default_no_orient_stays_unrotated(self, client, monkeypatch):
        """AC-5 负例 + AC-7:老 result(无 orient 字段)→ rot=0,落盘仍横幅(忘传 rot 必失败)。"""
        import core.pose as cp
        from app.api.v1.routes import chat as cr
        self._force_template(monkeypatch)
        from PIL import Image
        import io as _io
        seen = {}
        real = cr._frames_at_ts

        def spy(data, target_ts, rot=0):
            seen["rot"] = rot
            return real(data, target_ts, rot)
        monkeypatch.setattr(cr, "_frames_at_ts", spy)
        monkeypatch.setattr(cp, "analyze_video", lambda data, **kw: _mk_result())
        r = self._up(client, _synth_avi_rect(w=64, h=32))
        assert r.status_code == 200, r.text
        assert seen.get("rot") == 0
        fid = r.json()["data"]["frame_ids"][0]
        img = Image.open(_io.BytesIO(client.get(f"/api/v1/chat/images/{fid}").content))
        assert img.size == (32, 16)   # 源 64×32 未转正,crop(0.25..0.75) → 32×16

    def test_ok_log_carries_orient(self, client, monkeypatch, caplog):
        """FR-5:ok 日志带 orient/orient_conf;undetermined 同样打印(统计占比,不新增拒因)。"""
        import core.pose as cp
        self._force_template(monkeypatch)
        res = _mk_result()
        res.orient = {"orient": "undetermined", "orient_conf": 0.0, "orient_samples": 0,
                      "orient_abstain": 4, "rot_k": 0}
        res.quality["orient"], res.quality["orient_conf"] = "undetermined", 0.0
        monkeypatch.setattr(cp, "analyze_video", lambda data, **kw: res)
        with caplog.at_level("INFO"):
            r = self._up(client, _synth_avi())
        assert r.status_code == 200
        line = [l for l in caplog.messages if "evt=pose.analyze" in l and "result=ok" in l][0]
        assert "orient=undetermined" in line
        assert "朝向不可定" in r.json()["data"]["report"]
        assert r.json()["data"]["metrics"]["cadence_spm"] == 172.0  # 指标照常(FR-6)


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
