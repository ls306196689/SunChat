"""R-018 step-5 取证脚本(scripts/pose_live_capture.py)判定逻辑单测。

脚本本体是活体取证工具(HTTP 调用部分不在单测内),这里钉住它的 AC-6
判定纯函数 `judge()`——判据错了会让实拍对账的证据失真,必须可回归。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.pose_live_capture import CAD_HI, CAD_LO, judge  # noqa: E402


def _ok_body(orient="90cw", cad=165.0, pace="5:30/km", with_line=True, frames=("a.jpg",)):
    report = "画面已按人体朝向转正(头朝上,原为 %s)" % orient if with_line else "报告正文"
    return {"data": {
        "quality": {"orient": orient, "orient_conf": 0.9},
        "metrics": {"cadence_spm": cad, "pace": pace},
        "report": report,
        "frame_ids": list(frames),
        "report_source": "vlm",
        "message_id": 1,
    }}


class TestJudge:
    def test_all_pass_rotated(self):
        v = judge(200, _ok_body("270cw"))
        assert all(ok for ok, _ in v.values()), v

    def test_undetermined_flags_A_not_C(self):
        # 不可定 → A 判 FAIL(实拍要求非 undetermined),但 C 不强制转正行
        v = judge(200, _ok_body("undetermined", with_line=False))
        assert v["A_orient"][0] is False
        assert v["C_transparency"][0] is True

    def test_orient_0_upright_passes_A_no_line_needed(self):
        v = judge(200, _ok_body("0", with_line=False))
        assert v["A_orient"][0] is True and v["C_transparency"][0] is True

    def test_cadence_bounds(self):
        assert judge(200, _ok_body(cad=139.9))["B_cadence"][0] is False
        assert judge(200, _ok_body(cad=220.1))["B_cadence"][0] is False
        assert judge(200, _ok_body(cad=CAD_LO))["B_cadence"][0] is True
        assert judge(200, _ok_body(cad=CAD_HI))["B_cadence"][0] is True

    def test_missing_transparency_line_fails_C(self):
        # 转正档但报告漏印透明度行 → 必须 FAIL(FR-6 的活体面)
        assert judge(200, _ok_body("90cw", with_line=False))["C_transparency"][0] is False

    def test_no_frames_fails_D(self):
        assert judge(200, _ok_body(frames=()))["D_skeleton_frames"][0] is False

    def test_no_pace_fails_E(self):
        assert judge(200, _ok_body(pace=None))["E_pace"][0] is False

    def test_http_400_single_fail(self):
        v = judge(400, {"detail": "未检测到明显跑动段"})
        assert list(v) == ["A_orient"] and v["A_orient"][0] is False
        assert "400" in v["A_orient"][1] and "跑动" in v["A_orient"][1]
