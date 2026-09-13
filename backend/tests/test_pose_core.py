"""
R-017 P1 pose-core 单测 v2(离线确定性;MediaPipe 推理 monkeypatch 为合成关键点)
覆盖:AC-1(步频)、AC-7(死段稀释回归护栏)、AC-8(慢动作还原)、AC-9(配速三态)、
质量门槛(no_activity/low_conf/body_too_small)、probe 帧率探测(slo 容器真身,呼应 A-2)、
段采(FR-10)、机位无关性(D-3 护栏)。
夹具规范(checkpoint 教训):时间相干(死段零振荡/跑动段按真实时刻起振),
钉地几何 v5 教训:落点事件轴 land=(2j+side_off)·GAP,同脚跨 2 落点距,连续落点距=GAP。
"""
import io
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================== 合成步态世界模型(v2)====================

def _gait(t, f_hz, conf=0.9, body=0.6, run_start=0.0, hip_x=None, gap=None,
          duty=0.3, lift=0.16, x0=0.10):
    """时间 t(秒)→ 33 关键点(归一化,y 向下为正)。

    f_hz=单侧踝频率(两侧反相 0.5)→ 总步频=2f×60;t<run_start 站立(双腿分立零振荡)。
    gap≠None:钉落点几何(固定机位配速夹具)——stance 期踝画面 x 恒等于落点
    anchor=(2j+side_off)·gap,swing 期线性前移 2gap 落于下一 anchor;
    hip_x(t) 由夹具注入且速度恒 = 2·gap·f_hz(体心与落点流同步)。
    gap=None:钟摆几何(D-3/cadence 夹具,横穿靠 hip_x 整体平移)。
    """
    if run_start > 0 and t < run_start:
        hipy = 0.40
        lm = [(0.5, hipy, 0.0, conf)] * 33
        lm[11] = (0.46, hipy - 0.62 * body, 0.0, conf)
        lm[12] = (0.54, hipy - 0.62 * body, 0.0, conf)
        lm[23] = (0.47, hipy, 0.0, conf)
        lm[24] = (0.53, hipy, 0.0, conf)
        for side, ax in (("L", 0.44), ("R", 0.56)):
            lm[{"L": 27, "R": 28}[side]] = (ax, hipy + body * 0.45, 0.0, conf)
            lm[{"L": 25, "R": 26}[side]] = ((ax + 0.5) / 2, hipy + body * 0.22, 0.0, conf)
        return lm
    T = 1.0 / f_hz
    tr = t - run_start
    hipy = 0.40 - 0.02 * abs(math.sin(2 * math.pi * f_hz * tr))
    hipx = hip_x(t) if hip_x else 0.5
    lm = [(0.5, hipy, 0.0, conf)] * 33
    lm[11] = (hipx - 0.03, hipy - 0.62 * body, 0.0, conf)
    lm[12] = (hipx + 0.03, hipy - 0.62 * body, 0.0, conf)
    lm[23] = (hipx - 0.02, hipy, 0.0, conf)
    lm[24] = (hipx + 0.02, hipy, 0.0, conf)
    for side, off in (("L", 0.0), ("R", 0.5)):
        u = (tr - off * T) / T
        j = math.floor(u)
        p = u - j
        if gap is not None:
            anchor = x0 + (2 * j + (1 if side == "R" else 0)) * gap
            rel = 0.0 if p < duty else 2 * gap * (p - duty) / (1 - duty)
            ax = anchor + rel
        else:
            relx = 0.15 - 0.30 * (p / duty) if p < duty else \
                -0.15 + 0.30 * ((p - duty) / (1 - duty))
            ax = hipx + relx * 0.6
        lft = (0.0 if p < duty else lift * math.sin(math.pi * (p - duty) / (1 - duty))) * (body / 0.6)
        ay = hipy + body * 0.45 - lft
        lm[{"L": 27, "R": 28}[side]] = (ax, ay, 0.0, conf)
        lm[{"L": 25, "R": 26}[side]] = ((hipx + ax) / 2, (hipy + body * 0.45 + ay) / 2, 0.0, conf)
    return lm


def _mk(f_hz=1.5, dur=6.0, run_start=0.0, conf=0.9, body=0.6, hip_x=None, gap=None):
    return dict(f_hz=f_hz, dur=dur, run_start=run_start, conf=conf, body=body,
                hip_x=hip_x, gap=gap)


def _patch(monkeypatch, spec, probe=None):
    """注入 sample_frames(网格语义:fps/t0/t1/max_frames)+ probe_frames + 时间相干 detect。"""
    import core.pose as pose

    def fake_sample(data, fps=None, max_frames=None, t0=None, t1=None, width=0):
        a = float(t0 or 0.0)
        b = float(t1) if t1 is not None else spec["dur"]
        ts = []
        t = a
        while t <= b + 1e-9:
            ts.append(round(t, 6))
            t += 1.0 / float(fps or 20.0)
        if max_frames and len(ts) > max_frames:
            ts = [ts[j] for j in pose._resample_indices(len(ts), max_frames)]
        frames = [np.zeros((480, 640, 3), dtype=np.uint8) for _ in ts]
        return frames, ts, spec["dur"]

    def fake_detect(frames, ts=None):
        if ts is None:
            ts = [i / 20.0 for i in range(len(frames))]
        return [_gait(float(t), spec["f_hz"], spec["conf"], spec["body"],
                      spec["run_start"], spec.get("hip_x"), spec.get("gap"))
                for t in ts]

    monkeypatch.setattr(pose, "sample_frames", fake_sample)
    monkeypatch.setattr(pose, "_detect_landmarks", fake_detect)
    monkeypatch.setattr(pose, "probe_frames", probe or (lambda d: {
        "fps_eff": 25.0, "fps_nominal": 25.0, "slo_factor": 1, "vfr": False,
        "duration": spec["dur"]}))
    return pose


class TestAnalyze:
    def test_metrics_sine_cadence(self, monkeypatch):
        """AC-1 离线面:1.5Hz 双侧 → cad ≈ 180。"""
        r = _patch(monkeypatch, _mk()).analyze_video(b"x")
        assert r.metrics["cadence_spm"] == pytest.approx(180.0, rel=0.15), \
            f"cad={r.metrics['cadence_spm']}"

    def test_metric_keys_quality_v2(self, monkeypatch):
        r = _patch(monkeypatch, _mk()).analyze_video(b"x")
        assert set(("cadence_spm", "stance_swing_ratio", "knee_angle_at_contact_deg",
                    "knee_angle_at_toeoff_deg", "hip_rom_deg", "pelvic_tilt_deg",
                    "asymmetry_pct", "pace", "pace_reason")) <= set(r.metrics)
        assert r.quality["cycles"] >= 2 and 0 <= r.quality["score"] <= 1
        for k in ("fps_eff", "fps_nominal", "slo_factor", "vfr", "activity_span"):
            assert k in r.quality  # FR-8 透明度入 quality

    def test_stance_swing_ratio_geometry(self, monkeypatch):
        r = _patch(monkeypatch, _mk()).analyze_video(b"x")
        assert 0.2 < r.metrics["stance_swing_ratio"] <= 1.5

    def test_pace_null_when_height_unset(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "POSE_USER_HEIGHT_CM", 0.0)
        m = _patch(monkeypatch, _mk()).analyze_video(b"x").metrics
        assert m["pace"] is None and "身高" in m["pace_reason"]

    def test_low_conf_reject(self, monkeypatch):
        with pytest.raises(Exception) as e:
            _patch(monkeypatch, _mk(conf=0.2)).analyze_video(b"x")
        assert e.value.reason == "low_conf"

    def test_body_too_small_reject(self, monkeypatch):
        with pytest.raises(Exception) as e:
            _patch(monkeypatch, _mk(body=0.04)).analyze_video(b"x")
        assert e.value.reason == "body_too_small"

    def test_walk_no_activity(self, monkeypatch):
        """走路(≈102 spm < POSE_RUN_MIN_CAD=125)不得分析(FR-9 判跑门)。"""
        with pytest.raises(Exception) as e:
            _patch(monkeypatch, _mk(f_hz=0.85)).analyze_video(b"x")
        assert e.value.reason == "no_activity"

    def test_pure_stand_no_activity(self, monkeypatch):
        with pytest.raises(Exception) as e:
            _patch(monkeypatch, _mk(dur=4.0, run_start=99)).analyze_video(b"x")
        assert e.value.reason == "no_activity"

    def test_short_run_no_activity(self, monkeypatch):
        """跑动 < POSE_ACTIVITY_MIN_SEC → no_activity。"""
        with pytest.raises(Exception) as e:
            _patch(monkeypatch, _mk(dur=1.0)).analyze_video(b"x")
        assert e.value.reason == "no_activity"


class TestAc7DilutionGuard:
    """AC-7:前3s站立+后3s跑 vs 纯跑3s cadence 差≤5%(A-1 稀释回归永久护栏)。"""

    def test_dead_head_no_dilution(self, monkeypatch):
        c_pure = _patch(monkeypatch, _mk(dur=3.0, f_hz=1.5)).analyze_video(b"x").metrics["cadence_spm"]
        mix = _patch(monkeypatch, _mk(dur=6.0, f_hz=1.5, run_start=3.0)).analyze_video(b"x")
        assert mix.metrics["cadence_spm"] == pytest.approx(c_pure, rel=0.05), \
            f"pure={c_pure} mixed={mix.metrics['cadence_spm']}"
        assert mix.quality["activity_span"] <= 4.0  # 死段未入分母


class TestAc8SloRestore:
    """AC-8:slo×4 夹具(显示时长=真实×4)→ cadence 还原真值±10%,slo_factor=4。"""

    def test_slo_x4(self, monkeypatch):
        def probe_slo(d):
            return {"fps_eff": 6.25, "fps_nominal": 25.0, "slo_factor": 4,
                    "vfr": False, "duration": 24.0}
        # 真实 1.5Hz 跑 → 显示时间轴 0.375Hz(dense fps=min(25,6.25)=6.25 采样)
        spec = _mk(f_hz=0.375, dur=20.0)
        r = _patch(monkeypatch, spec, probe=probe_slo).analyze_video(b"x")
        assert r.quality["slo_factor"] == 4
        assert r.metrics["cadence_spm"] == pytest.approx(180.0, rel=0.10), \
            f"slo 还原失败 cad={r.metrics['cadence_spm']}"


class TestAc9Pace:
    """AC-9:pace 三态(固定机位夹具 v 自洽/随机位、未配身高 null+原因)。"""

    # 物理标定:body 高≈0.49 归一化=235px↔175cm;腿≈0.45×0.6×480=129.6px↔92.75cm
    # → m/px=0.007157;GAP=0.125=80px→步长≈0.573m,cad180→v≈1.72m/s(6:25/km 级)
    GAP, F = 0.125, 1.5

    def _fixed_rig(self, monkeypatch, height=175.0, dur=2.5):
        from app.config import settings
        monkeypatch.setattr(settings, "POSE_USER_HEIGHT_CM", height)
        slope = 2 * self.GAP * self.F  # 体心速度=落点流速度(钉地语义,锚点始终在髋下)
        spec = _mk(f_hz=self.F, dur=dur, hip_x=lambda t: 0.06 + slope * t, gap=self.GAP)
        return _patch(monkeypatch, spec)

    def test_fixed_camera_pace(self, monkeypatch):
        r = self._fixed_rig(monkeypatch).analyze_video(b"x")
        p = r.metrics["pace"]
        assert p is not None, f"应输出配速 reason={r.metrics['pace_reason']}"
        assert p["height_cm"] == pytest.approx(175.0)  # R-8:报告打印所用身高
        mpp_true = 0.53 * 1.75 / (0.45 * 0.6 * 480)
        v_true = self.GAP * 640 * mpp_true * 180.0 / 60.0
        assert p["v_ms"] == pytest.approx(v_true, rel=0.25), \
            f"v={p['v_ms']} 期望≈{v_true:.2f}"

    def test_follow_camera_null(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "POSE_USER_HEIGHT_CM", 175.0)
        m = _patch(monkeypatch, _mk(dur=4.0)).analyze_video(b"x").metrics  # 髋心无横移
        assert m["pace"] is None
        assert "横移" in m["pace_reason"] or "跑步机" in m["pace_reason"]

    def test_height_unset_null(self, monkeypatch):
        m = self._fixed_rig(monkeypatch, height=0.0).analyze_video(b"x").metrics
        assert m["pace"] is None and "身高" in m["pace_reason"]


class TestCameraInvariance:
    """D-cadence 永久护栏:固定机位横穿 vs 跟随,cadence 一致(D-3 根因)。"""

    def _rig(self, monkeypatch, move):
        spec = _mk(f_hz=1.5, dur=6.0, hip_x=(lambda t: 0.2 + 0.06 * t) if move else None)
        return _patch(monkeypatch, spec)

    def test_traverse_cadence(self, monkeypatch):
        r = self._rig(monkeypatch, True).analyze_video(b"x")
        assert r.metrics["cadence_spm"] == pytest.approx(180.0, rel=0.15)

    def test_traverse_equals_follow(self, monkeypatch):
        c_fixed = self._rig(monkeypatch, True).analyze_video(b"x").metrics["cadence_spm"]
        c_follow = self._rig(monkeypatch, False).analyze_video(b"x").metrics["cadence_spm"]
        assert c_fixed == pytest.approx(c_follow, rel=0.05)


class TestProbe:
    """FR-8(analysis A-2):元数据不可信,f_eff=PTS 实测;slo 容器倍速判定。"""

    def _avi(self, rate=30, stretch=1, n=120):
        import av
        from fractions import Fraction
        buf = io.BytesIO()
        c = av.open(buf, "w", format="avi")
        st = c.add_stream("mjpeg", rate=rate)
        st.width = st.height = 96
        st.pix_fmt = "yuvj420p"
        tb = Fraction(1, rate)
        for i in range(n):
            arr = np.full((96, 96, 3), (i * 7) % 255, np.uint8)
            f = av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(format="yuvj420p")
            f.pts = i * stretch
            f.time_base = tb
            for p in st.encode(f):
                c.mux(p)
        for p in st.encode():
            c.mux(p)
        c.close()
        return buf.getvalue()

    def test_probe_normal(self):
        from core.pose import probe_frames
        q = probe_frames(self._avi(30, 1, 90))
        assert q["fps_eff"] == pytest.approx(30.0, rel=0.05)
        assert q["slo_factor"] == 1 and q["vfr"] is False
        assert q["duration"] == pytest.approx(3.0, abs=0.1)

    def test_probe_slo_x8_nominal240(self):
        """标称240 + PTS×8(显示30)→ N=8(A-2 容器语义;avg_rate 可能谎报)。"""
        from core.pose import probe_frames
        q = probe_frames(self._avi(240, 8, 240))
        assert q["fps_eff"] == pytest.approx(30.0, rel=0.1)
        assert q["fps_nominal"] == pytest.approx(240.0, rel=0.05)
        assert q["slo_factor"] == 8

    def test_probe_garbage_never_raises(self):
        from core.pose import probe_frames
        q = probe_frames(b"definitely not a video")
        assert q["fps_eff"] > 0 and q["slo_factor"] == 1


class TestLocate:
    def test_run_window_with_dead_head(self):
        from core.pose import locate_activity
        ts = [i / 5.0 for i in range(60)]
        lms = [_gait(t, 1.5, run_start=6.0) for t in ts]
        segs = locate_activity(lms, ts)
        assert segs, "应检出跑动段"
        best = max(segs, key=lambda s: s[1] - s[0])
        # 粗扫窗(1s/0.5s步进)边界粒度 ±1s,允许提前量;死段大头(0~5s)不入段
        assert best[0] >= 4.5, f"死段头泄漏: {segs}"

    def test_pure_stand_no_segments(self):
        from core.pose import locate_activity
        ts = [i / 5.0 for i in range(40)]
        lms = [_gait(t, 1.5, run_start=99) for t in ts]
        assert locate_activity(lms, ts) == []


class TestSampling:
    def test_max_frames_resample_keeps_endpoints(self):
        from core.pose import _resample_indices
        sel = _resample_indices(1000, 400)
        assert len(sel) == 400 and sel[0] == 0 and sel[-1] == 999

    def _avi(self, rate=30, n=30, w=96, h=96):
        import av
        buf = io.BytesIO()
        c = av.open(buf, "w", format="avi")
        st = c.add_stream("mjpeg", rate=rate)
        st.width, st.height, st.pix_fmt = w, h, "yuvj420p"
        for i in range(n):
            arr = np.zeros((h, w, 3), dtype=np.uint8)
            arr[:, :, i % 3] = 200
            c.mux(st.encode(av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(format="yuvj420p")))
        c.mux(st.encode())
        c.close()
        return buf.getvalue()

    def test_sample_frames_real_synth_avi(self):
        import core.pose as pose
        frames, ts, dur = pose.sample_frames(self._avi(), fps=20.0, max_frames=400)
        assert len(frames) in (20, 21) and ts[0] == 0.0 and dur > 0.9
        assert frames[0].shape[2] == 3

    def test_segment_window_only_decodes_range(self):
        import core.pose as pose
        frames, ts, _ = pose.sample_frames(self._avi(30, 90), fps=10.0, t0=2.0, t1=3.0)
        assert ts and all(1.8 <= t <= 3.1 for t in ts)
        assert 5 <= len(ts) <= 15

    def test_downscale_width(self):
        import core.pose as pose
        frames, _, _ = pose.sample_frames(self._avi(15, 15, 320, 240), fps=5.0, width=160)
        assert frames[0].shape[1] == 160
