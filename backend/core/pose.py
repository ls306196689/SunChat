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
    crop_bbox: Optional[Tuple[float, float, float, float]] = None  # FR-12 归一化 xyxy,None=整帧


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
                  max_frames: Optional[int] = None, t0: Optional[float] = None,
                  t1: Optional[float] = None, width: int = 0):
    """视频字节 → (RGB np 帧列表, 时间戳秒, 时长秒)。超 max_frames 自动加大步距。

    R-017v2:t0/t1=仅采该段(FR-10 fast-seek,段外不解);width>0 时降采样(粗扫提速)。
    """
    import av
    from app.config import settings
    fps = float(fps or settings.POSE_SAMPLE_FPS)
    max_frames = int(max_frames or settings.POSE_MAX_SAMPLE_FRAMES)

    c = av.open(io.BytesIO(data))
    frames, ts = [], []
    try:
        st = c.streams.video[0]
        rate = float(st.average_rate) if st.average_rate else 25.0
        tb = float(st.time_base) if st.time_base else 1.0 / rate
        if t0 is not None:
            try:
                c.seek(max(0, int(t0 / tb)), stream=st, backward=True)
            except TypeError:  # 旧版 PyAV 位置参签名
                c.seek(max(0, int(t0 / tb)), st)
        step = 1.0 / fps
        next_t = float(t0) if t0 else 0.0
        i = 0
        for f in c.decode(video=0):
            t = float(f.pts * f.time_base) if (f.pts is not None and f.time_base) else i / rate
            if t1 is not None and t > t1 + 1e-9:
                break
            if t >= next_t - 1e-9:
                img = f.to_image()
                if width and img.width > width:
                    img = img.resize((width, max(1, round(img.height * width / img.width))))
                frames.append(np.asarray(img.convert("RGB")))
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


# ==================== 帧率探测(R-017v2 FR-8,analysis A-2)====================

def probe_frames(data: bytes) -> dict:
    """demux 全量 packet PTS(不解码)→ 真实显示帧率/名义帧率/慢动作倍速/VFR 标记。

    元数据不可信(avg_rate 在 slo 容器下谎报,A-2);f_eff=1/PTS 中位间隔。
    慢动作:倍速 N=round(名义/f_eff)∈{2,4,8} 且标称≥240(手机慢动作档位)才认定,
    宁可漏判不误伤常速素材。PyAV 无 container.time_base,时长用 PTS 跨度反推。
    """
    import av
    out = {"fps_eff": 25.0, "fps_nominal": 0.0, "slo_factor": 1,
           "vfr": False, "duration": 0.0}
    try:
        c = av.open(io.BytesIO(data))
    except Exception:
        return out
    try:
        st = c.streams.video[0]
        nominal = float(st.average_rate) if st.average_rate else 0.0
        tb = float(st.time_base)
        pts = [pkt.pts for pkt in c.demux(st)
               if pkt is not None and pkt.pts is not None]
        if nominal:
            out["fps_nominal"] = round(nominal, 2)
        if len(pts) >= 4 and tb > 0:
            d = np.diff(np.sort(np.asarray(pts, dtype=float)))
            d = d[d > 0]
            if len(d) >= 3:
                med = float(np.median(d))
                out["fps_eff"] = round(1.0 / (med * tb), 2)
                out["duration"] = round((float(pts[-1] - pts[0]) + med) * tb, 3)
                mean = float(np.mean(d))
                if mean > 0:
                    out["vfr"] = bool(float(np.std(d)) / mean > 0.35)  # R-10
                if nominal >= 240:  # FR-8 慢动作档判定
                    n = round(nominal / out["fps_eff"]) if out["fps_eff"] > 0 else 1
                    out["slo_factor"] = n if n in (2, 4, 8) else 1
            elif st.duration:
                out["duration"] = round(float(st.duration) * tb, 3)
        elif st.duration and tb > 0:
            out["duration"] = round(float(st.duration) * tb, 3)
    except Exception as e:
        logger.warning(f"probe_frames fallback: {e}")
    finally:
        c.close()
    return out


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


def _detect_landmarks(frames: List[np.ndarray],
                      ts: Optional[List[float]] = None) -> List[Optional[List[LM]]]:
    """逐帧单人体 33 关键点;无人帧 None。单测 monkeypatch 本函数。

    粗扫/密采两路都走此注入面;ts=帧时间戳(秒),合成夹具据此产出时间相干关键点
    (站立段无振荡、跑动段按真实时刻起振)——v1 dwell 夹具教训:无时间轴必失配。
    """
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
                  lo: float = 0.25, hi: float = 1.25, min_lag: int = 3):
    """去均值自相关,lag∈[lo,hi]s 找主周期(D-3:固定机位下世界速度法失效的替代)。

    min_lag:候选下限钳制(v2:防去趋势/短窗平滑产生的"自身窗"边峰假阳性)。
    返回 (lag帧数, 归一化相关值);信号无周期/太短 → None。"""
    n = len(sig)
    if n < 8 or fps <= 0:
        return None
    x = sig - float(np.mean(sig))
    e = float(np.dot(x, x))
    if e <= 1e-12:
        return None
    ac = np.correlate(x, x, mode="full")[n - 1:] / e
    l0 = max(int(lo * fps) + 1, min_lag, 1)
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


def _segment(lms: list, det: List[int], ts_a: np.ndarray, min_cycles: int,
             slo: int = 1):
    """→ (cycles, ic_r, ic_l)。D-3:主周期取髋竖直信号(双腿共因、比踝更稳),
    左右踝 y 各自按区间法切stance;周期以多数侧的 IC 为界。
    slo:慢动作倍速——显示周期=N×真实,主周期搜索窗随 N 放大(否则 lag 找不到,
    半步伪分不漏合、IC 计数虚增,AC-8)。"""
    pos_t = ts_a[det]
    fps = (len(pos_t) - 1) / max(float(pos_t[-1] - pos_t[0]), 1e-6)
    hip_y = _smooth(np.asarray([lms[i][IDX["L_hip"]][1] for i in det]), w=3)
    dl = _dominant_lag(hip_y - _smooth(hip_y, w=5), fps, hi=1.25 * max(1, int(slo)))
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


# ==================== 关键段定位(R-017v2 FR-9,analysis A-1)====================

def locate_activity(lms: list, ts, slo: int = 1) -> List[Tuple[float, float, float]]:
    """粗扫关键点 → 跑动段 [(t0, t1, energy)],能量降序累计≤POSE_MAX_SEGMENT_SEC。

    两级判据(FR-9 落地形态):(a) 全局 FFT 定频——踝y去趋势后主频换算真实步频
    须∈[POSE_RUN_MIN_CAD,240](走路≈100-120、站立无频峰被滤;slo 容器显示频率
    ÷N,故 ×N 还原判定);(b) 1s 滑窗能量——|踝y振荡|/腿长≥0.06 的窗口连成段。
    实现注:FR-9 原文"窗内自相关定频"在 5fps 采样下欠采样(180spm 周期 3.3帧,
    1s 窗=5样本无法测相关),故频域判定移到全局轨迹(样本量=全片),窗只判能量。
    合并 <0.3s 邻段;死段由此剔除,指标分母=跑动段(修 A-1,AC-7)。
    """
    from app.config import settings
    slo = max(1, int(slo))
    ts = np.asarray(ts, dtype=float)
    det = [i for i, l in enumerate(lms) if l]
    if len(det) < 8:
        return []
    dts = np.diff(ts[det])
    dts = dts[dts > 1e-9]
    if not len(dts):
        return []
    fps = 1.0 / float(np.median(dts))
    dtrend = int(max(2.5, 1.6 * slo) * fps) | 1

    ank = {s: _smooth(np.asarray([lms[i][IDX[f"{s}_ankle"]][1] for i in det]), w=3)
           for s in ("L", "R")}
    hip_y = np.asarray([lms[i][IDX["L_hip"]][1] for i in det])
    leg = np.maximum(np.abs(np.minimum(ank["L"], ank["R"]) - hip_y), 1e-3)
    med_leg = float(np.median(leg))

    # (a) 判跑频带不在粗扫做:5fps 带通重建处于混叠区不可靠(⚠R-7 证实,debug-log
    #     D-4);走路同有振荡会过能量门,统一由 analyze_video 密采后终判频带门拒之。

    # (b) 1s 窗能量门 → 段:站立死段踝y恒定位,raw std 严格为 0(不 detrend 是为
    #     杜绝泄漏过渡窗把段头吃进死段,AC-7 边界收紧到 1 个过渡窗)
    win = max(4, int(round(1.0 * fps)))
    hop = max(1, int(round(0.5 * fps)))
    wins = []
    n = len(det)
    k = 0
    while k + win <= n:
        sl = slice(k, k + win)
        t0, t1 = float(ts[det[k]]), float(ts[det[k + win - 1]])
        k += hop
        if t1 - t0 > 3.2 * win / fps:  # 窗过稀(大空窗),跳过
            continue
        rel = max(float(np.std(ank[s][sl])) for s in ("L", "R")) / med_leg
        if rel >= 0.04:
            wins.append((t0, t1, rel))
    if not wins:
        return []
    wins.sort()
    merged = [list(wins[0])]
    for a, b, s in wins[1:]:
        if a - merged[-1][1] < 0.3:
            merged[-1][1] = max(merged[-1][1], b)
            merged[-1][2] = max(merged[-1][2], s)
        else:
            merged.append([a, b, s])
    merged.sort(key=lambda m: m[2] * (m[1] - m[0]), reverse=True)
    out, total = [], 0.0
    for a, b, s in merged[:2]:
        b = min(b, a + settings.POSE_MAX_SEGMENT_SEC)  # 单段截断(能量前部优先)
        if total + (b - a) > settings.POSE_MAX_SEGMENT_SEC and out:
            break
        out.append((round(a, 3), round(b, 3), round(s, 4)))
        total += b - a
    return out


# ==================== 配速(R-017v2 FR-11,analysis A-3)====================

def _pace(groups: list, frame_hw, cad_spm, height_cm: float):
    """跑动段关键点 → (pace dict | None, reason | None)。

    前提:身高已配置(FR-11)+ 固定机位(髋中心x跨度≥0.8×身高px;随机位横移为0
    不可解,跑步机同)+ 髋连线倾角<15°(R-9,俯拍距离失真)。
    方法:腿长px(髋-膝+膝-踝 双腿 stance 帧中值,刚性)→ m/px 自标定;钉地落点
    (IC 事件时刻踝 x)排序相邻距中值=步长;v=步长×cad/60。
    """
    import statistics
    if not cad_spm or cad_spm <= 0:
        return None, "步频未测得,不输出配速"
    if not height_cm or height_cm <= 0:
        return None, "身高未配置(POSE_USER_HEIGHT_CM=0),不输出配速"
    H, W = frame_hw[0], frame_hw[1]
    cx, legs, tilts, contacts = [], [], [], []
    ymax, ymin = [], []
    for (lms, det, ts_a, cycles, ic_r, ic_l) in groups:
        # 落点 = 各事件 IC 时刻踝 x(钉地瞬间,画面坐标);跨段合并排序
        for ev_ic, side in ((ic_r, "R"), (ic_l, "L")):
            for (s0, s1) in ev_ic:
                idxs = [k for k in det if s0 - 1e-9 <= ts_a[k] <= s1 + 1e-9]
                if not idxs:
                    continue
                k0 = min(idxs, key=lambda k: abs(ts_a[k] - s0))
                contacts.append(lms[k0][IDX[f"{side}_ankle"]][0] * W)
                # 腿长标定只用 stance 帧(摆动期膝提踝抬,腿线失真)
                for k in idxs:
                    hip, knee, ankle = (lms[k][IDX[f"{side}_hip"]],
                                        lms[k][IDX[f"{side}_knee"]],
                                        lms[k][IDX[f"{side}_ankle"]])
                    pxy = H / W
                    legs.append((math.dist((hip[0], hip[1] * pxy), (knee[0], knee[1] * pxy)) +
                                 math.dist((knee[0], knee[1] * pxy), (ankle[0], ankle[1] * pxy))) * W)
        for i in det:
            lh, rh = lms[i][IDX["L_hip"]], lms[i][IDX["R_hip"]]
            cx.append((lh[0] + rh[0]) / 2 * W)
            dx = (rh[0] - lh[0]) * W
            dy = (rh[1] - lh[1]) * H
            if math.hypot(dx, dy) > 1.0:
                tilts.append(math.degrees(math.atan2(dy, dx)))
            ys_all = [p[1] for p in lms[i]]
            ymin.append(min(ys_all))
            ymax.append(max(ys_all))
    if not cx or not legs:
        return None, "关键点不足,不输出配速"
    body_h_px = float(np.median(np.asarray(ymax) - np.asarray(ymin))) * H
    hip_span = float(np.max(cx) - np.min(cx))
    if hip_span < 0.8 * body_h_px:
        return None, "未检出画面横移(随机位跟随/跑步机),配速不可解"
    if tilts and abs(statistics.median(tilts)) > 15:  # R-9
        return None, "机位倾斜>15°,水平距离失真,不输出配速"
    leg_px = float(np.median(legs))
    if leg_px <= 1:
        return None, "腿长标定失败"
    m_per_px = 0.53 * (height_cm / 100.0) / leg_px
    cs = sorted(contacts)
    if len(cs) < 4:
        return None, "钉地落点不足,不输出配速"
    gaps = [b - a for a, b in zip(cs, cs[1:]) if b - a > 0.5]
    if not gaps:
        return None, "落点间距无效"
    step_m = float(np.median(gaps)) * m_per_px
    v = step_m * cad_spm / 60.0
    if not (0.5 <= v <= 12.0):
        return None, f"配速估计越界({v:.2f}m/s),不可信"
    min_per_km = 1000.0 / (v * 60.0)  # 分钟/km(小数)
    mm = int(min_per_km)
    ss = int(round((min_per_km - mm) * 60))
    return {"v_ms": round(v, 2), "kmh": round(v * 3.6, 2),
            "min_per_km": round(min_per_km, 2),
            "pace_str": f"{mm}:{ss:02d}", "stride_m": round(step_m, 3),
            "height_cm": round(height_cm, 1)}, None


# ==================== 指标(R-017v2:分母=跑动段,修 A-1 稀释)====================

_EMPTY = {k: None for k in METRIC_KEYS}


def _metrics(groups: list, span: float) -> dict:
    """groups: [(lms, det, ts_a, cycles, ic_r, ic_l)] 每跑动段一组。

    cadence 分母=段内触地点覆盖跨度(相邻 IC 计 (n-1)/span,死段头无 IC 不虚增);
    多段合并 Σ(n_i−1)/Σspan_i。ssr/asym 为周期比值,天然段内。"""
    if not groups or span <= 1e-6:
        return dict(_EMPTY)
    n_ic, cov, tot_ic = 0, 0.0, 0
    for (_lms, _det, _ts, _cy, icr, icl) in groups:
        ics = sorted([s for s, _ in icr] + [s for s, _ in icl])
        tot_ic += len(ics)
        if len(ics) >= 2 and ics[-1] > ics[0]:
            n_ic += len(ics) - 1
            cov += ics[-1] - ics[0]
    cadence = (n_ic / cov * 60.0) if cov > 1e-6 else (tot_ic / span * 60.0)

    cycles = [c for g in groups for c in g[3]]
    st_r = [e["toe_off_r"] - e["initial_contact_r"] for c in cycles
            for e in [c.events] if "toe_off_r" in e and "initial_contact_r" in e]
    st_l = [e["toe_off_l"] - e["initial_contact_l"] for c in cycles
            for e in [c.events] if "toe_off_l" in e and "initial_contact_l" in e]
    ssr = None
    if cycles:
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

    knee_c, knee_t, hips, tilts = [], [], [], []
    for (lms, det, ts_a, cyc, _icr, _icl) in groups:
        def at(t, lmname, _l=lms, _d=det, _t=ts_a):
            j = min(_d, key=lambda d: abs(_t[d] - t))
            return _l[j][IDX[lmname]]

        for c in cyc:
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
        for i in det:  # 骨盆侧倾:髋连线与水平夹角(冠状面近似;正=左髋偏高)
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


# ==================== 主入口(R-017v2:probe→粗扫→locate→段内密采→段内事件)====================

def analyze_video(data: bytes, *, max_sample_frames: Optional[int] = None) -> PoseResult:
    """视频字节 → PoseResult。质量不过 raise PoseQualityError(no_activity/low_conf/...)。

    v2 流水线(FR-8~12):probe 真实帧率 → 粗扫(5fps@256px)定位跑动段 → 段内密采
    (25fps)切分指标(分母=段,修 A-1)→ 慢动作×N 还原 → 条件配速 → 关键点 bbox 并集裁剪。
    """
    from app.config import settings
    probe = probe_frames(data)
    f_eff = probe["fps_eff"] or 25.0
    slo = max(1, int(probe.get("slo_factor", 1)))

    co_fps = min(settings.POSE_COARSE_FPS, f_eff)
    frames_c, ts_c, dur = sample_frames(data, fps=co_fps,
                                        max_frames=max_sample_frames, width=256)
    if not frames_c:
        raise PoseQualityError("no_cycles", "未能解出任何帧")
    lms_c = _detect_landmarks(frames_c, ts_c)
    det_c = [i for i, l in enumerate(lms_c) if l]

    coverage = len(det_c) / len(lms_c)
    mean_conf = float(np.mean([p[3] for i in det_c for p in lms_c[i]])) if det_c else 0.0
    if coverage < 0.6 or mean_conf < settings.POSE_MIN_CONF:
        raise PoseQualityError("low_conf",
                               f"关键点置信度不足(conf={mean_conf:.2f},检出率={coverage:.0%})")
    body_ratio = float(np.mean([max(p[1] for p in lms_c[i]) - min(p[1] for p in lms_c[i])
                                for i in det_c])) if det_c else 0.0
    if body_ratio < settings.POSE_MIN_BODY_RATIO:
        raise PoseQualityError("body_too_small", f"人体占画面过小({body_ratio:.2f})")

    segs = locate_activity(lms_c, ts_c, slo=slo)
    total_seg = sum(b - a for a, b, _ in segs)
    if total_seg < settings.POSE_ACTIVITY_MIN_SEC:
        raise PoseQualityError(
            "no_activity", "未检测到明显跑动段(站立/走路不计;跑动步频需≥%.0f步/分且≥%.1fs)"
            % (settings.POSE_RUN_MIN_CAD, settings.POSE_ACTIVITY_MIN_SEC))

    den_fps = min(settings.POSE_DENSE_FPS, f_eff)
    den_max = int(max_sample_frames or settings.POSE_MAX_SAMPLE_FRAMES)
    per_seg_budget = max(8, den_max // max(len(segs), 1))  # 两段均分上限,总预算不超
    groups, ld_all, ts_all = [], [], []
    last_hw = (frames_c[0].shape[0], frames_c[0].shape[1])
    conf_d = []
    for a, b, _e in segs:
        fd, tsd, _ = sample_frames(data, fps=den_fps, max_frames=per_seg_budget, t0=a, t1=b)
        if not fd:
            continue
        last_hw = (fd[0].shape[0], fd[0].shape[1])
        ld = _detect_landmarks(fd, tsd)
        dd = [i for i, l in enumerate(ld) if l]
        if not dd:
            continue
        ts_ad = np.asarray(tsd)
        cyc, icr, icl = _segment(ld, dd, ts_ad, settings.POSE_MIN_CYCLES, slo=slo)
        groups.append((ld, dd, ts_ad, cyc, icr, icl))
        ld_all.extend(ld)
        ts_all.extend(tsd)
        conf_d.extend(p[3] for i in dd for p in ld[i])

    all_cycles = [c for g in groups for c in g[3]]
    if len(all_cycles) < settings.POSE_MIN_CYCLES:
        raise PoseQualityError("no_cycles",
                               f"步态周期不足({len(all_cycles)}<{settings.POSE_MIN_CYCLES}),"
                               "请跑过相机前方 2s 以上")

    # FR-12 裁剪框:关键点并集 +10% margin;短边 <256px 则整帧(裁剪失语境)
    H, W = last_hw
    xs = [p[0] for (ld, dd, *_r) in groups for i in dd for p in ld[i]]
    ys = [p[1] for (ld, dd, *_r) in groups for i in dd for p in ld[i]]
    crop = None
    if xs and ys:
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if (x1 - x0) * W >= 256 and (y1 - y0) * H >= 256:
            mx, my = (x1 - x0) * 0.1, (y1 - y0) * 0.1
            crop = (round(max(0.0, x0 - mx), 4), round(max(0.0, y0 - my), 4),
                    round(min(1.0, x1 + mx), 4), round(min(1.0, y1 + my), 4))

    metrics = _metrics(groups, total_seg)
    if metrics.get("cadence_spm") is not None and slo > 1 and settings.POSE_SLO_RESTORE:
        metrics["cadence_spm"] = round(metrics["cadence_spm"] * slo, 1)  # FR-8 还原
    # 判跑终门(密采带内可靠;粗扫 5fps 频带死区 R-7 的终判位,debug-log D-4):
    # 走路≈100~120 spm 与站立由此拒之 no_activity
    cad_fin = metrics.get("cadence_spm")
    if cad_fin is None or not (settings.POSE_RUN_MIN_CAD <= cad_fin <= 240.0):
        raise PoseQualityError(
            "no_activity", "未检测到明显跑动(步频 %.0f 不在跑带 [%.0f,240],走路不计)"
            % (cad_fin or 0, settings.POSE_RUN_MIN_CAD))
    pace_obj, pace_reason = _pace(groups, last_hw, metrics.get("cadence_spm"),
                                  settings.POSE_USER_HEIGHT_CM)
    metrics["pace"] = pace_obj
    metrics["pace_reason"] = pace_reason

    if conf_d:
        mean_conf = float(np.mean(conf_d))
    quality = {"mean_conf": round(mean_conf, 3), "body_ratio": round(body_ratio, 3),
               "cycles": len(all_cycles),
               "score": round(mean_conf * 0.7 + min(body_ratio / 0.3, 1.0) * 0.3, 3),
               "fps_eff": probe["fps_eff"], "fps_nominal": probe["fps_nominal"],
               "slo_factor": slo, "vfr": probe["vfr"],
               "activity_span": round(total_seg, 2)}
    return PoseResult(metrics=metrics, quality=quality, cycles=all_cycles,
                      landmarks_seq=ld_all, sample_ts=ts_all,
                      video_duration=round(dur or probe["duration"], 3),
                      crop_bbox=crop)
