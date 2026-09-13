"""
SunChat Backend - Running Pose Analysis P1 pose-core (R-017)
采样(PyAV)→MediaPipe 关键点→步态切分(踝低速区间法)→7 指标。

单测注入面:_detect_landmarks(monkeypatch 为合成关键点,离线确定性,R-009 whisper 惯例)。
"""
import io
import math
import os
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from utils.logger import logger

LM = Tuple[float, float, float, float]  # (x, y, z, visibility) 归一化坐标

IDX = {"L_shoulder": 11, "R_shoulder": 12, "L_hip": 23, "R_hip": 24,
       "L_knee": 25, "R_knee": 26, "L_ankle": 27, "R_ankle": 28}

METRIC_KEYS = ("cadence_spm", "stance_swing_ratio", "knee_angle_at_contact_deg",
               "knee_angle_at_toeoff_deg", "hip_rom_deg", "pelvic_tilt_deg",
               "asymmetry_pct")


@dataclass
class Cycle:
    t0: float
    t1: float
    events: dict = field(default_factory=dict)
    cadence_spm: Optional[float] = None


@dataclass
class PoseResult:
    metrics: dict
    quality: dict
    cycles: list
    landmarks_seq: list
    sample_ts: list
    video_duration: float


class PoseQualityError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(reason)


# ==================== 采样 ====================

def _resample_indices(n: int, k: int) -> List[int]:
    """n 个点等距降为 k 个(保首末,去重保序)。"""
    if k >= n:
        return list(range(n))
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


def sample_frames(data: bytes, fps: Optional[float] = None,
                  max_frames: Optional[int] = None):
    """视频字节 → (RGB np 帧列表, 时间戳秒, 时长秒)。超 max_frames 自动加大步距。"""
    import av
    from app.config import settings
    fps = float(fps or settings.POSE_SAMPLE_FPS)
    max_frames = int(max_frames or settings.POSE_MAX_SAMPLE_FRAMES)

    c = av.open(io.BytesIO(data))
    frames, ts = [], []
    try:
        st = c.streams.video[0]
        rate = float(st.average_rate) if st.average_rate else 25.0
        step = 1.0 / fps
        next_t = 0.0
        i = 0
        for f in c.decode(video=0):
            t = float(f.pts * f.time_base) if (f.pts is not None and f.time_base) else i / rate
            if t >= next_t - 1e-9:
                frames.append(np.asarray(f.to_image().convert("RGB")))
                ts.append(t)
                next_t += step
                while next_t <= t + 1e-9:  # 网格追赶,防漂移欠采
                    next_t += step
            i += 1
    finally:
        c.close()
    duration = ts[-1] + 1.0 / rate if ts else 0.0
    if len(frames) > max_frames:
        sel = _resample_indices(len(frames), max_frames)
        frames = [frames[j] for j in sel]
        ts = [ts[j] for j in sel]
    return frames, ts, duration


# ==================== MediaPipe 推理(进程单例+锁,R-6)====================

_lock = threading.Lock()
_landmarker = None


def _get_landmarker():
    global _landmarker
    with _lock:
        if _landmarker is None:
            from app.config import settings
            from mediapipe.tasks import python as mpp
            from mediapipe.tasks.python import vision
            path = os.path.abspath(settings.POSE_MODEL_PATH)
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            _landmarker = vision.PoseLandmarker.create_from_options(
                vision.PoseLandmarkerOptions(
                    base_options=mpp.BaseOptions(model_asset_path=path),
                    running_mode=vision.RunningMode.IMAGE,
                    num_poses=1))
        return _landmarker


def _detect_landmarks(frames: List[np.ndarray]) -> List[Optional[List[LM]]]:
    """逐帧单人体 33 关键点;无人帧 None。单测 monkeypatch 本函数。"""
    from mediapipe import Image, ImageFormat
    lm = _get_landmarker()
    out = []
    for arr in frames:
        with _lock:
            r = lm.detect(Image(image_format=ImageFormat.SRGB,
                                data=np.ascontiguousarray(arr)))
        pts = r.pose_landmarks[0] if r.pose_landmarks else None
        out.append(None if pts is None else
                   [(p.x, p.y, p.z, p.visibility) for p in pts])
    return out


# ==================== 几何与切分 ====================

def _smooth(v: np.ndarray, w: int = 3) -> np.ndarray:
    if len(v) < w:
        return v
    k = np.ones(w) / w
    pad = w // 2
    return np.convolve(np.pad(v, pad, mode="edge"), k, mode="valid")


def _angle(a, b, c) -> float:
    """∠ABC 度数(0~180)。"""
    v1 = np.asarray(a[:2], dtype=float) - np.asarray(b[:2], dtype=float)
    v2 = np.asarray(c[:2], dtype=float) - np.asarray(b[:2], dtype=float)
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return float("nan")
    cosang = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return math.degrees(math.acos(cosang))


def _dominant_lag(sig: np.ndarray, fps: float,
                  lo: float = 0.25, hi: float = 1.25):
    """去均值自相关,lag∈[lo,hi]s 找主周期(D-3:固定机位下世界速度法失效的替代)。

    返回 (lag帧数, 归一化相关值);信号无周期/太短 → None。"""
    n = len(sig)
    if n < 8 or fps <= 0:
        return None
    x = sig - float(np.mean(sig))
    e = float(np.dot(x, x))
    if e <= 1e-12:
        return None
    ac = np.correlate(x, x, mode="full")[n - 1:] / e
    l0 = max(int(lo * fps) + 1, 1)
    l1 = min(int(hi * fps) + 1, n - 1)
    if l1 <= l0:
        return None
    seg = ac[l0:l1]
    i = int(np.argmax(seg))
    return l0 + i, float(seg[i])


def _detrend(sig: np.ndarray, win: int) -> np.ndarray:
    win = max(3, int(win) | 1)
    return sig - _smooth(sig, w=win)


def _stance_intervals(sig: np.ndarray, ts: np.ndarray, lag=None, k_sigma=0.35,
                      min_stance=0.04, min_edge=0.10) -> List[Tuple[float, float]]:
    """踝竖直序列(画面 y,向下为正;落地=高值)→ [(IC, TO), ...]。

    D-3 重做:旧"世界坐标低速=stance"仅在相机跟随跑者时成立,固定机位侧拍踝从
    不静止 → 检出噪声(cadence 54 实测)。现法:以自相关主周期 lag 为窗去趋势
    (消机位倾斜与身体慢晃),y > μ+kσ 区间即触地期;IC=入区,TO=出区。
    """
    if len(sig) < 4:
        return []
    s = _smooth(np.asarray(sig, dtype=float), w=3)
    if lag:
        s = _detrend(s, win=lag)
    mu, sd = float(np.mean(s)), float(np.std(s))
    if sd <= 1e-9:
        return []
    inb = s > mu + k_sigma * sd
    out, start = [], None
    for i, v in enumerate(inb):
        if v and start is None:
            start = float(ts[i])
        elif not v and start is not None:
            if (float(ts[i]) - start >= min_stance and
                    start - float(ts[0]) >= min_edge):
                out.append((start, float(ts[i])))
            start = None
    # 半步伪分合并:相邻区间间距 < 0.35*周期窗(或无窗口时 <0.12s)视为同一次触地
    if out:
        mgap = 0.35 * (lag / (len(ts) / max(ts[-1] - ts[0], 1e-6))) if lag and lag > 1 else 0.12
        merged = [out[0]]
        for a, b in out[1:]:
            if a - merged[-1][1] < mgap:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        out = merged
    return out


def _side_ankle_y(lms: list, det: List[int], side: str) -> np.ndarray:
    return np.asarray([lms[i][IDX[side + "_ankle"]][1] for i in det])


def _segment(lms: list, det: List[int], ts_a: np.ndarray, min_cycles: int):
    """→ (cycles, ic_r, ic_l)。D-3:主周期取髋竖直信号(双腿共因、比踝更稳),
    左右踝 y 各自按区间法切stance;周期以多数侧的 IC 为界。"""
    pos_t = ts_a[det]
    fps = (len(pos_t) - 1) / max(float(pos_t[-1] - pos_t[0]), 1e-6)
    hip_y = _smooth(np.asarray([lms[i][IDX["L_hip"]][1] for i in det]), w=3)
    dl = _dominant_lag(hip_y - _smooth(hip_y, w=5), fps)
    lag = dl[0] if (dl and dl[1] > 0.25) else None
    ic_r = _stance_intervals(_side_ankle_y(lms, det, "R"), pos_t, lag=lag)
    ic_l = _stance_intervals(_side_ankle_y(lms, det, "L"), pos_t, lag=lag)
    cycles, base = [], ic_r if len(ic_r) >= len(ic_l) else ic_l
    other = ic_l if base is ic_r else ic_r
    is_r = base is ic_r
    if len(base) < 2:
        return [], ic_r, ic_l
    for i in range(len(base) - 1):
        t0, t1 = base[i][0], base[i + 1][0]
        if t1 - t0 <= 0:
            continue
        m = "_" + ("r" if is_r else "l")
        o = "l" if is_r else "r"
        ev = {f"initial_contact{m}": t0, f"toe_off{m}": base[i][1],
              "cadence_primary": True}
        for (s0, s1) in other:
            if t0 <= s0 < t1:
                ev[f"initial_contact_{o}"] = s0
                ev[f"toe_off_{o}"] = s1
                break
        cycles.append(Cycle(t0=round(t0, 4), t1=round(t1, 4), events=ev,
                            cadence_spm=60.0 / (t1 - t0)))
    return cycles, ic_r, ic_l


# ==================== 指标 ====================

_EMPTY = {k: None for k in METRIC_KEYS}


def _metrics(lms: list, det: List[int], ts_a: np.ndarray,
             cycles: List[Cycle], ic_r, ic_l) -> dict:
    if not det or not cycles:
        return dict(_EMPTY)

    def at(t, lmname):
        j = min(det, key=lambda d: abs(ts_a[d] - t))
        return lms[j][IDX[lmname]]

    span = max(float(ts_a[det[-1]] - ts_a[det[0]]), 1e-6)
    ic_all = [s for s, _ in ic_r] + [s for s, _ in ic_l]
    ic_in = [t for t in ic_all if ts_a[det[0]] - 1e-9 <= t <= ts_a[det[-1]] + 1e-9]
    cadence = len(ic_in) / span * 60.0

    st_r = [e["toe_off_r"] - e["initial_contact_r"] for c in cycles
            for e in [c.events] if "toe_off_r" in e and "initial_contact_r" in e]
    st_l = [e["toe_off_l"] - e["initial_contact_l"] for c in cycles
            for e in [c.events] if "toe_off_l" in e and "initial_contact_l" in e]
    ssr = None
    T = float(np.mean([c.t1 - c.t0 for c in cycles]))
    if st_r and T > 0:
        mr = float(np.mean(st_r))
        if T - mr > 1e-6:
            ssr = round(mr / (T - mr), 3)
    asym = None
    if st_r and st_l:
        mr, ml = float(np.mean(st_r)), float(np.mean(st_l))
        if mr + ml > 0:
            asym = round(abs(mr - ml) / ((mr + ml) / 2) * 100, 1)

    knee_c, knee_t, hips = [], [], []
    for c in cycles:
        e = c.events
        for side in ("R", "L"):
            ic, to = e.get(f"initial_contact_{side.lower()}"), e.get(f"toe_off_{side.lower()}")
            if ic is not None:
                knee_c.append(_angle(at(ic, f"{side}_hip"), at(ic, f"{side}_knee"),
                                     at(ic, f"{side}_ankle")))
            if to is not None:
                knee_t.append(_angle(at(to, f"{side}_hip"), at(to, f"{side}_knee"),
                                     at(to, f"{side}_ankle")))
        seg = [i for i in det if c.t0 <= ts_a[i] <= c.t1]
        if len(seg) >= 3:
            for side in ("R", "L"):
                angs = [a for a in (_angle(lms[i][IDX[f"{side}_shoulder"]],
                                           lms[i][IDX[f"{side}_hip"]],
                                           lms[i][IDX[f"{side}_knee"]]) for i in seg)
                        if not math.isnan(a)]
                if angs:
                    hips.append(max(angs) - min(angs))

    # 骨盆侧倾:髋连线与水平夹角(冠状面近似;正=左髋偏高)
    tilts = []
    for i in det:
        lh, rh = lms[i][IDX["L_hip"]], lms[i][IDX["R_hip"]]
        dx, dy = rh[0] - lh[0], rh[1] - lh[1]
        if dx > 1e-4:  # 侧视可见髋宽才可信
            tilts.append(math.degrees(math.atan2(dy, dx)))
    fin = lambda v: round(float(np.nanmean(v)), 1) if len(v) else None
    return {
        "cadence_spm": round(float(cadence), 1),
        "stance_swing_ratio": ssr,
        "knee_angle_at_contact_deg": fin(knee_c),
        "knee_angle_at_toeoff_deg": fin(knee_t),
        "hip_rom_deg": fin(hips),
        "pelvic_tilt_deg": round(float(np.mean(tilts)), 1) if tilts else None,
        "asymmetry_pct": asym,
    }


# ==================== 主入口 ====================

def analyze_video(data: bytes, *, max_sample_frames: Optional[int] = None) -> PoseResult:
    """视频字节 → PoseResult。质量不过 raise PoseQualityError(reason='low_conf'等)。"""
    from app.config import settings
    frames, ts, duration = sample_frames(data, max_frames=max_sample_frames)
    if not frames:
        raise PoseQualityError("no_cycles", "未能解出任何帧")
    lms = _detect_landmarks(frames)
    det = [i for i, l in enumerate(lms) if l]

    coverage = len(det) / len(lms)
    mean_conf = float(np.mean([p[3] for i in det for p in lms[i]])) if det else 0.0
    if coverage < 0.6 or mean_conf < settings.POSE_MIN_CONF:
        raise PoseQualityError("low_conf",
                               f"关键点置信度不足(conf={mean_conf:.2f},检出率={coverage:.0%})")

    body_ratio = float(np.mean([max(p[1] for p in lms[i]) - min(p[1] for p in lms[i])
                                for i in det]))
    if body_ratio < settings.POSE_MIN_BODY_RATIO:
        raise PoseQualityError("body_too_small", f"人体占画面过小({body_ratio:.2f})")

    ts_a = np.asarray(ts)
    cycles, ic_r, ic_l = _segment(lms, det, ts_a, settings.POSE_MIN_CYCLES)
    if len(cycles) < settings.POSE_MIN_CYCLES:
        raise PoseQualityError("no_cycles",
                               f"步态周期不足({len(cycles)}<{settings.POSE_MIN_CYCLES}),请跑过相机前方 2s 以上")

    metrics = _metrics(lms, det, ts_a, cycles, ic_r, ic_l)
    quality = {"mean_conf": round(mean_conf, 3), "body_ratio": round(body_ratio, 3),
               "cycles": len(cycles),
               "score": round(mean_conf * 0.7 + min(body_ratio / 0.3, 1.0) * 0.3, 3)}
    return PoseResult(metrics=metrics, quality=quality, cycles=cycles,
                      landmarks_seq=lms, sample_ts=ts, video_duration=round(duration, 3))
