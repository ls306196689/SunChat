"""
SunChat Backend - Pose Skeleton P2 pose-skeleton (R-017)
相位选帧 + 骨架叠加(触地侧红/摆动侧绿)。纯函数,无 IO。
"""
from typing import List, Tuple

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


def draw_skeleton(rgb_frame: np.ndarray, landmarks: list) -> np.ndarray:
    """33 点骨架叠加。返回新帧(uint8 RGB)。"""
    from PIL import Image, ImageDraw
    h, w = rgb_frame.shape[:2]
    img = Image.fromarray(np.asarray(rgb_frame, dtype=np.uint8))
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
