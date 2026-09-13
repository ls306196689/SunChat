"""
R-017 P1 pose-core 单测(离线确定性;MediaPipe 推理 monkeypatch 为合成关键点)
覆盖:AC-1(离线面)步频、质量三门槛、采样降步距、周期不足拒析、几何角度、
机位无关性(D-3 回归护栏:固定机位横穿 vs 相机跟随,cadence 必须一致)。
"""
import io
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _gait_x(ph: float) -> float:
    """相位[0,1) → 踝世界x:dwell 0.45(静止 0.30)+ 快摆 0.55(0.30→0.65)。"""
    return 0.30 if ph < 0.45 else 0.30 + 0.35 * (ph - 0.45) / 0.55


def _fake_landmarks(t: float, f_hz: float, conf: float, body_scale: float) -> list:
    """33 点合成步态:f_hz=单侧踝频率(两侧反相0.5),总步频=2f×60。"""
    ph = (f_hz * t) % 1.0
    hip_y = 0.92 - body_scale * 0.45
    sh_y = hip_y - body_scale * 0.40
    lm = [(0.5, hip_y, 0.0, conf)] * 33
    lm[11] = (0.46, sh_y, 0.0, conf)
    lm[12] = (0.54, sh_y, 0.0, conf)
    lm[23] = (0.47, hip_y, 0.0, conf)
    lm[24] = (0.53, hip_y, 0.0, conf)
    for side, off in (("L", 0.0), ("R", 0.5)):
        p = (ph + off) % 1.0
        ax = 0.5 + (_gait_x(p) - 0.475) * body_scale
        ay = hip_y + body_scale * 0.43 * (1.0 - (0.0 if p < 0.45 else 0.07 * math.sin(math.pi * (p - 0.45) / 0.55)))
        kx = 0.5 + (ax - 0.5) * 0.5
        ky = hip_y + body_scale * 0.22
        lm[{"L": 27, "R": 28}[side]] = (ax, ay, 0.0, conf)
        lm[{"L": 25, "R": 26}[side]] = (kx, ky, 0.0, conf)
    return lm


def _patch_pipeline(monkeypatch, n=120, fps=20.0, f_hz=1.5, conf=0.9,
                    body_scale=0.6, cover=1.0):
    import core.pose as pose

    fps_val = fps

    def fake_sample(data, fps=None, max_frames=None):
        ts = [i / fps_val for i in range(n)]
        frames = [np.zeros((480, 640, 3), dtype=np.uint8) for _ in range(n)]
        return frames, ts, n / fps_val

    def fake_detect(frames):
        out = []
        for i in range(len(frames)):
            miss = cover < 1.0 and (i % max(2, int(1 / max(cover, 1e-6)))) == 1
            out.append(None if miss else _fake_landmarks(i / fps, f_hz, conf, body_scale))
        return out

    monkeypatch.setattr(pose, "sample_frames", fake_sample)
    monkeypatch.setattr(pose, "_detect_landmarks", fake_detect)
    return pose


class TestAnalyze:
    """R-017/AC-1(离线面)"""

    def test_metrics_sine_cadence(self, monkeypatch):
        """双侧反相 1.5Hz → 总步频≈180 步/分(rel 25% 容差,边界 IC 截断损耗)。"""
        pose = _patch_pipeline(monkeypatch, n=120, fps=20.0, f_hz=1.5)
        r = pose.analyze_video(b"x")
        assert r.metrics["cadence_spm"] == pytest.approx(180.0, rel=0.25), \
            f"cadence={r.metrics['cadence_spm']}"
        T = r.cycles[0].t1 - r.cycles[0].t0
        assert T == pytest.approx(1 / 1.5, rel=0.25)

    def test_7_metric_keys_and_quality(self, monkeypatch):
        pose = _patch_pipeline(monkeypatch)
        r = pose.analyze_video(b"x")
        assert set(pose.METRIC_KEYS) <= set(r.metrics.keys())
        assert r.quality["cycles"] >= 2 and 0 <= r.quality["score"] <= 1
        assert r.quality["mean_conf"] == pytest.approx(0.9, abs=0.01)

    def test_stance_swing_ratio_geometry(self, monkeypatch):
        """夹具占空比 0.45 → ssr 物理合理区间(平滑边界损耗容差内)。"""
        pose = _patch_pipeline(monkeypatch, f_hz=1.5)
        r = pose.analyze_video(b"x")
        assert 0.3 < r.metrics["stance_swing_ratio"] <= 1.5

    def test_knee_angle_plausible(self, monkeypatch):
        """跑姿几何:接触时刻膝近伸(100~175°),非折腿。"""
        pose = _patch_pipeline(monkeypatch, body_scale=0.6)
        r = pose.analyze_video(b"x")
        kc = r.metrics["knee_angle_at_contact_deg"]
        assert kc is not None and 100 < kc < 175

    def test_low_conf_reject(self, monkeypatch):
        pose = _patch_pipeline(monkeypatch, conf=0.2)
        with pytest.raises(pose.PoseQualityError) as e:
            pose.analyze_video(b"x")
        assert e.value.reason == "low_conf"

    def test_low_coverage_reject(self, monkeypatch):
        pose = _patch_pipeline(monkeypatch, cover=0.4)
        with pytest.raises(pose.PoseQualityError) as e:
            pose.analyze_video(b"x")
        assert e.value.reason == "low_conf"

    def test_body_too_small_reject(self, monkeypatch):
        pose = _patch_pipeline(monkeypatch, body_scale=0.04)
        with pytest.raises(pose.PoseQualityError) as e:
            pose.analyze_video(b"x")
        assert e.value.reason == "body_too_small"

    def test_no_cycles_reject(self, monkeypatch):
        pose = _patch_pipeline(monkeypatch, n=50, fps=20.0, f_hz=0.5)
        with pytest.raises(pose.PoseQualityError) as e:
            pose.analyze_video(b"x")
        assert e.value.reason == "no_cycles"


# ---- D-3 回归护栏:固定机位横穿 vs 相机跟随,cadence 必须一致 ----
# 根因复盘:旧 _stance_intervals 用踝世界速度定 stance,仅相机跟随时成立;真实
# 侧拍固定机位,踝世界 x 全程递增 → 旧法 cadence 实测 54(D-cadence)。

def _traverse_landmarks(t, fps, f_hz, conf, body_move):
    """单腿 f_hz、反相步态;body_move=True=身体横穿画面(固定机位),False=居中(跟随机位)。

    踝竖直 ay 由步态相位决定(stance贴地/swing上抬),水平 ax 随 body_move 递增。
    cadence 物理值 = 2 × f_hz × 60,与 body_move 无关。
    """
    hipy = 0.42 - 0.03 * abs(math.sin(2 * math.pi * f_hz * t))
    hipx = (0.25 + 0.12 * t) if body_move else 0.5
    lm = [(0.5, hipy, 0.0, conf)] * 33
    lm[11] = (hipx - 0.03, hipy - 0.22, 0.0, conf)
    lm[12] = (hipx + 0.03, hipy - 0.22, 0.0, conf)
    lm[23] = (hipx - 0.02, hipy, 0.0, conf)
    lm[24] = (hipx + 0.02, hipy, 0.0, conf)
    for side, off in (("L", 0.0), ("R", 0.5)):
        p = (f_hz * t + off) % 1.0
        relx = 0.15 - 0.30 * (p / 0.4) if p < 0.4 else -0.15 + 0.30 * ((p - 0.4) / 0.6)
        lift = 0.0 if p < 0.4 else 0.16 * math.sin(math.pi * (p - 0.4) / 0.6)
        ax = hipx + relx * 0.6
        ay = hipy + 0.45 - lift
        lm[{"L": 27, "R": 28}[side]] = (ax, ay, 0.0, conf)
        lm[{"L": 25, "R": 26}[side]] = ((hipx + ax) / 2, (hipy + 0.45 + ay) / 2 - 0.01, 0.0, conf)
    return lm


def _patch_traverse(monkeypatch, body_move):
    import core.pose as pose
    N, F, FH = 140, 20.0, 1.5

    def fake_sample(data, fps=None, max_frames=None):
        return ([np.zeros((480, 640, 3), np.uint8) for _ in range(N)],
                [i / F for i in range(N)], N / F)

    def fake_detect(frames):
        return [_traverse_landmarks(i / F, F, FH, 0.9, body_move) for i in range(len(frames))]

    monkeypatch.setattr(pose, "sample_frames", fake_sample)
    monkeypatch.setattr(pose, "_detect_landmarks", fake_detect)
    return pose, 2 * FH * 60  # 期望 cadence=180


class TestCameraInvariance:
    """AC-1 强化(D-cadence 修复):机位移动不得影响步频。"""

    def test_fixed_camera_traverse_cadence(self, monkeypatch):
        pose, expect = _patch_traverse(monkeypatch, body_move=True)
        r = pose.analyze_video(b"x")
        assert r.metrics["cadence_spm"] == pytest.approx(expect, rel=0.15), \
            f"固定机位 cadence={r.metrics['cadence_spm']} 期望≈{expect}"

    def test_traverse_equals_follow_cadence(self, monkeypatch):
        p1, e = _patch_traverse(monkeypatch, body_move=True)
        c_fixed = p1.analyze_video(b"x").metrics["cadence_spm"]
        p2, _ = _patch_traverse(monkeypatch, body_move=False)
        c_follow = p2.analyze_video(b"x").metrics["cadence_spm"]
        assert c_fixed == pytest.approx(c_follow, rel=0.05), \
            f"机位无关性违背 fixed={c_fixed} follow={c_follow}"



class TestSampling:
    def test_max_frames_resample_keeps_endpoints(self):
        from core.pose import _resample_indices
        sel = _resample_indices(1000, 400)
        assert len(sel) == 400 and sel[0] == 0 and sel[-1] == 999
        assert sel == sorted(sel)

    def test_sample_frames_real_synth_avi(self):
        import core.pose as pose
        import av
        buf = io.BytesIO()
        c = av.open(buf, "w", format="avi")
        st = c.add_stream("mjpeg", rate=30)
        st.width, st.height, st.pix_fmt = 96, 96, "yuvj420p"
        for i in range(30):
            arr = np.zeros((96, 96, 3), dtype=np.uint8)
            arr[:, :, i % 3] = 200
            c.mux(st.encode(av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(format="yuvj420p")))
        c.mux(st.encode())
        c.close()
        frames, ts, dur = pose.sample_frames(buf.getvalue(), fps=20.0, max_frames=400)
        assert len(frames) in (20, 21) and ts[0] == 0.0 and dur > 0.9
        assert frames[0].shape[2] == 3
        f2, ts2, _ = pose.sample_frames(buf.getvalue(), fps=60.0, max_frames=8)
        assert len(f2) == 8 and ts2[0] == 0.0
