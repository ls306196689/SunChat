"""
SunChat Backend - Pose Skeleton P2 pose-skeleton (R-017)
相位选帧 + 骨架叠加(触地侧红/摆动侧绿)。纯函数,无 IO。
"""
from typing import List, Optional, Tuple

import numpy as np

from core.pose import IDX, PoseResult

# MediaPipe 33 点骨架连线(躯干+四肢)
EDGES = [(11, 12), (11, 23), (12, 24), (23, 24),
         (11, 13), (13, 15), (12, 14), (14, 16),          # 手臂
         (23, 25), (25, 27), (24, 26), (26, 28)]          # 腿

PHASES = ("initial_contact", "midstance", "toe_off", "swing")


def select_key_frames(result: PoseResult, k: int = 4) -> List[Tuple[int, str]]:
    """相位代表帧 → [(landmarks_seq 下标, 相位标签)],相位尽量互异。"""
    ts = np.asarray(result.sample_ts)
    picked, used = [], set()

    def pick(t: float, label: str):
        i = int(np.argmin(np.abs(ts - t)))
        if result.landmarks_seq[i] is None or i in used:
            return False
        used.add(i)
        picked.append((i, label))
        return True

    full = [c for c in result.cycles if any(k2.startswith("initial_contact") for k2 in c.events)]
    for c in (full or result.cycles)[:2]:
        e = c.events
        for ph in PHASES[:3]:
            for side in ("_r", "_l"):
                key = f"{ph}{side}"
                if key in e and len(picked) < k:
                    if pick(e[key], ph):
                        break
        if len(picked) >= k:
            break
    # swing 补足(周期中点)
    for c in result.cycles:
        if len(picked) >= k:
            break
        if pick((c.t0 + c.t1) / 2, "swing"):
            continue
    return picked[:k]


def draw_skeleton(rgb_frame: np.ndarray, landmarks: list,
                  crop_bbox: Optional[Tuple[float, float, float, float]] = None) -> np.ndarray:
    """33 点骨架叠加。返回新帧(uint8 RGB)。

    crop_bbox=归一化(xyxy,R-017v2 FR-12)时先裁剪再绘制(躯干占比≥60% 交 VLM);
    None=旧行为整帧绘制。关键点归一化坐标在裁剪系内重映射。
    """
    from PIL import Image, ImageDraw
    arr = np.asarray(rgb_frame, dtype=np.uint8)
    h, w = arr.shape[:2]
    if crop_bbox is not None:
        x0, y0, x1, y1 = crop_bbox
        px0, py0, px1, py1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
        px0, py0 = max(0, min(px0, w - 1)), max(0, min(py0, h - 1))
        px1, py1 = max(px0 + 1, min(px1, w)), max(py0 + 1, min(py1, h))
        arr = arr[py0:py1, px0:px1]
        h, w = arr.shape[:2]
        landmarks = [((p[0] - x0) / max(x1 - x0, 1e-6),
                      (p[1] - y0) / max(y1 - y0, 1e-6), p[2], p[3]) for p in landmarks]
    img = Image.fromarray(arr.copy())
    d = ImageDraw.Draw(img)
    pts = [(p[0] * w, p[1] * h) for p in landmarks]

    def seg(a, b, color, width):
        d.line([pts[a], pts[b]], fill=color, width=width)

    # 躯干白、骨盆加粗
    seg(11, 12, (255, 255, 255), 2)
    seg(23, 24, (255, 255, 255), 4)
    seg(11, 23, (255, 255, 255), 2)
    seg(12, 24, (255, 255, 255), 2)
    for arm in ((11, 13), (13, 15), (12, 14), (14, 16)):
        seg(*arm, (200, 200, 200), 2)
    # 双腿:踝 visibility 高(着地侧)红,低摆侧绿——visibility 近似相位可靠度,
    # 更稳判据:踝 y 更低(更贴地=画面下)为 stance 侧。
    ly = landmarks[IDX["L_ankle"]][1]
    ry = landmarks[IDX["R_ankle"]][1]
    stance_side = "L" if ly >= ry else "R"
    for side in ("L", "R"):
        hip, knee, ankle = (IDX[f"{side}_hip"], IDX[f"{side}_knee"], IDX[f"{side}_ankle"])
        color = (225, 29, 72) if side == stance_side else (22, 163, 74)
        seg(hip, knee, color, 3)
        seg(knee, ankle, color, 3)
    for i, (x, y) in enumerate(pts):
        if i in (11, 12, 23, 24, 25, 26, 27, 28):
            r = 3
            d.ellipse([x - r, y - r, x + r, y + r], fill=(250, 204, 21))
    return np.asarray(img)
