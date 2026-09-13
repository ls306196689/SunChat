"""R-017 P3 pose-report 单测:VL 双路+降级(AC-4)+模板规则(llm 注入,零网络)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pose import PoseResult  # noqa: E402
from core.pose_report import build_report, summary_text, template_report  # noqa: E402


def _mk(metrics=None):
    m = metrics or {"cadence_spm": 172.5, "stance_swing_ratio": 0.8,
                    "knee_angle_at_contact_deg": 158.0, "knee_angle_at_toeoff_deg": 61.0,
                    "hip_rom_deg": 52.0, "pelvic_tilt_deg": 3.2, "asymmetry_pct": 4.1}
    return PoseResult(metrics=m, quality={"score": 0.83}, cycles=[], landmarks_seq=[],
                      sample_ts=[], video_duration=3.2)


class FakeLLM:
    def __init__(self, text=None, boom=False):
        self.text, self.boom, self.calls = text, boom, []

    def chat(self, messages, **kw):
        self.calls.append((messages, kw))
        if self.boom:
            raise TimeoutError("ollama down")
        return {"message": {"content": self.text}}


class TestVlPath:
    def test_vl_success(self):
        llm = FakeLLM(text="教练报告正文")
        text, src = build_report(_mk(), ["eImFn=="], llm=llm, vision_ok=True)
        assert src == "vl" and "教练报告" in text
        sent, kw = llm.calls[0]
        assert sent[1]["images"] == ["eImFn=="]
        assert "172.5" in sent[1]["content"]
        assert kw.get("timeout")  # POSE_REPORT_TIMEOUT 传递 [AC FR-5]

    def test_vl_timeout_falls_back_to_template(self):
        """AC-4 核心:VL 异常→template,永不抛出。"""
        text, src = build_report(_mk(), ["b64"], llm=FakeLLM(boom=True), vision_ok=True)
        assert src == "template" and "172.5" in text

    def test_vl_empty_content_falls_back(self):
        text, src = build_report(_mk(), ["b64"], llm=FakeLLM(text="   "), vision_ok=True)
        assert src == "template"

    def test_no_vision_direct_template(self):
        """AC-4:无 VL 直接模板,llm 零调用。"""
        llm = FakeLLM(text="不该被调")
        text, src = build_report(_mk(), ["b64"], llm=llm, vision_ok=False)
        assert src == "template" and llm.calls == []

    def test_vl_but_no_frames_template(self):
        llm = FakeLLM(text="x")
        text, src = build_report(_mk(), [], llm=llm, vision_ok=True)
        assert src == "template"


class TestTemplate:
    def test_all_metrics_present_with_none_entries(self):
        r = _mk({"cadence_spm": 150.0, "stance_swing_ratio": None,
                 "knee_angle_at_contact_deg": 175.0, "knee_angle_at_toeoff_deg": None,
                 "hip_rom_deg": None, "pelvic_tilt_deg": 12.0, "asymmetry_pct": 15.0})
        t = template_report(r)
        assert t.count("未测得") == 3
        # 规则触发:不对称>10 / 步频<160 / 着地膝过伸>170 / 骨盆侧倾>8
        for frag in ("弱侧", "步频", "微屈", "臀中肌"):
            assert frag in t
        assert "非医疗建议" in t

    def test_healthy_metrics_no_hints(self):
        t = template_report(_mk())
        assert "暂无突出风险项" in t

    def test_summary_text_lists_7_keys(self):
        s = summary_text(_mk().metrics)
        assert len(s.splitlines()) == 7
