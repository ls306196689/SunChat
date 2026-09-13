"""R-017 P2 pose-skeleton 单测(纯合成 PoseResult,零模型依赖)"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pose import Cycle, PoseResult  # noqa: E402
from core.pose_skeleton import draw_skeleton, select_key_frames  # noqa: E402


def _mk_lm(t: float, conf=0.9):
    lm = [(0.5, 0.5, 0.0, conf)] * 33
    lm[27] = (0.4 + 0.1 * np.sin(t), 0.9, 0.0, conf)
    lm[28] = (0.6 + 0.1 * np.sin(t + 3.14), 0.88 + 0.02 * np.sin(t), 0.0, conf)
    return lm


def _mk_result(n=40, cycles=None):
    ts = [i / 20 for i in range(n)]
    if cycles is None:
        cycles = [Cycle(0.3, 0.97, {"initial_contact_r": 0.3, "toe_off_r": 0.6,
                                    "midstance_r": 0.45, "initial_contact_l": 0.63,
                                    "toe_off_l": 0.9}, 96.0),
                  Cycle(0.97, 1.63, {"initial_contact_r": 0.97, "toe_off_r": 1.27,
                                     "midstance_r": 1.12, "initial_contact_l": 1.3,
                                     "toe_off_l": 1.55}, 97.0)]
    return PoseResult(metrics={}, quality={}, cycles=cycles,
                      landmarks_seq=[_mk_lm(t) for t in ts],
                      sample_ts=ts, video_duration=n / 20)


class TestSelectKeyFrames:
    def test_phases_mutually_distinct_and_unique_frames(self):
        r = _mk_result()
        picked = select_key_frames(r, k=4)
        assert len(picked) == 4
        idxs = [i for i, _ in picked]
        assert len(set(idxs)) == 4, "帧不重复"
        labels = [lab for _, lab in picked]
        assert len(set(labels)) >= 3, f"相位尽量互异: {labels}"

    def test_k_insufficient_cycles_swing_fill(self):
        one = [Cycle(0.3, 0.9, {"initial_contact_r": 0.3}, 100.0)]
        r = _mk_result(cycles=one)
        picked = select_key_frames(r, k=4)
        assert 1 <= len(picked) <= 4
        assert any(lab == "swing" for _, lab in picked)

    def test_none_frames_skipped(self):
        r = _mk_result()
        r.landmarks_seq[6] = None  # IC_r=0.3s → idx 6
        picked = select_key_frames(r, k=4)
        assert all(i != 6 for i, _ in picked)


class TestDrawSkeleton:
    def test_output_different_and_shape(self):
        base = np.zeros((480, 640, 3), dtype=np.uint8)
        out = draw_skeleton(base, _mk_lm(0.3))
        assert out.shape == base.shape and out.dtype == np.uint8
        assert out.sum() > base.sum(), "骨架线应有非零像素"

    def test_input_not_mutated(self):
        base = np.ones((100, 100, 3), dtype=np.uint8) * 7
        snap = base.copy()
        draw_skeleton(base, _mk_lm(0.1))
        assert np.array_equal(base, snap), "draw 不得改原帧"

    def test_crop_bbox_smaller_output_and_redraw(self):
        """R-017v2 FR-12:crop_bbox(归一化xyxy)→ 输出=裁剪区尺寸,骨架仍绘出。"""
        base = np.zeros((480, 640, 3), dtype=np.uint8)
        out = draw_skeleton(base, _mk_lm(0.3), crop_bbox=(0.25, 0.0, 0.75, 0.5))
        assert out.shape == (240, 320, 3)
        assert out.sum() > 0, "裁剪图上骨架线应有非零像素"

    def test_crop_landmarks_remapped_into_view(self):
        """关键点落在裁剪区 → 必有像素级绘制(锚点重映射正确,不会整体出画)。"""
        base = np.zeros((480, 640, 3), dtype=np.uint8)
        lm = _mk_lm(0.3)
        whole = draw_skeleton(base, lm)
        c = (0.0, 0.5, 1.0, 1.0)  # 下半屏(踝所在)
        cropped = draw_skeleton(base, lm, crop_bbox=c)
        assert cropped.shape == (240, 640, 3)
        assert cropped.sum() > 0

    def test_crop_degenerate_clamped(self):
        """越界/退化 bbox 钳制,不抛异常。"""
        base = np.zeros((120, 160, 3), dtype=np.uint8)
        out = draw_skeleton(base, _mk_lm(0.3), crop_bbox=(-0.2, -0.1, 1.3, 0.02))
        assert out.ndim == 3 and out.shape[2] == 3 and out.shape[0] >= 1
