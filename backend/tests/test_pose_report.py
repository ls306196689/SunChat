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


class TestTransparencyV2:
    """R-017v2 FR-8/9/12 透明度行 + pace 三态文案。"""

    def _mk_q(self, quality=None, pace=None, reason=None):
        from core.pose import PoseResult
        m = {"cadence_spm": 170.0, "stance_swing_ratio": 0.8,
             "knee_angle_at_contact_deg": 158.0, "knee_angle_at_toeoff_deg": 61.0,
             "hip_rom_deg": 52.0, "pelvic_tilt_deg": 3.2, "asymmetry_pct": 4.1,
             "pace": pace, "pace_reason": reason}
        return PoseResult(metrics=m, quality=quality or {}, cycles=[],
                          landmarks_seq=[], sample_ts=[], video_duration=3.2)

    def test_transparency_lines_rendered_in_template(self):
        from core.pose_report import template_report, transparency_lines
        r = self._mk_q(quality={"fps_eff": 29.97, "fps_nominal": 240.0, "slo_factor": 8,
                                "vfr": True, "activity_span": 3.4},
                      pace={"v_ms": 2.6, "kmh": 9.4, "min_per_km": 6.41,
                            "pace_str": "6:25", "stride_m": 0.91, "height_cm": 175.0})
        tl = transparency_lines(r)
        joined = "\n".join(tl)
        assert "29.97fps" in joined and "慢动作×8" in joined and "3.4s" in joined
        assert "可变帧率" in joined and "6:25/km" in joined and "175.0cm" in joined
        t = template_report(r)
        assert "分析帧率≈29.97fps" in t

    def test_pace_reason_line_when_null(self):
        from core.pose_report import template_report
        r = self._mk_q(reason="身高未配置(POSE_USER_HEIGHT_CM=0),不输出配速")
        t = template_report(r)
        assert "配速: 未输出" in t and "身高未配置" in t

    def test_vl_prompt_carries_context(self):
        llm = FakeLLM(text="ok")
        r = self._mk_q(quality={"fps_eff": 25.0, "activity_span": 2.2})
        build_report(r, ["b64"], llm=llm, vision_ok=True)
        content = llm.calls[0][0][1]["content"]
        assert "跑动分析段 2.2s" in content
