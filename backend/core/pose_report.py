"""
SunChat Backend - Pose Report P3 pose-report (R-017)
指标+骨架帧 → VL 教练报告(决策 D-002);无 VL/失败 → 确定性模板报告。
"""
from typing import List, Optional, Tuple

from utils.logger import log_event, logger

SYSTEM = (
    "你是专业跑步姿态教练。用户会给出跑姿量化指标(单位见字段名)与 3~4 张带骨架标注的"
    "跑姿帧(红线=支撑侧腿,绿线=摆动侧腿)。请输出三段中文报告:"
    "①量化指标解读(逐项对照大众跑者参考范围);②左右对称性与潜在伤病风险;"
    "③改进建议 3~5 条(可执行 drills)。措辞谨慎,提及伤病时建议咨询专业人士。"
    "不要编造未给出的数据。"
)

_RULE_HINTS = [
    ("asymmetry_pct", lambda v: v is not None and v > 10,
     "左右腿触地时间差异超过 10%,建议关注弱侧肌力与旧伤,必要时做单腿稳定训练或咨询运动医学科"),
    ("cadence_spm", lambda v: v is not None and v < 160,
     "步频偏低,可尝试节拍器逐步提高到 170~180 步/分,缩短跨步、减小着地冲击"),
    ("stance_swing_ratio", lambda v: v is not None and v > 2.5,
     "触地时间偏长,注意蹬伸发力与小腿刚性,"
     "可加入跳绳/A 跳提升反应力量"),
    ("knee_angle_at_contact_deg", lambda v: v is not None and v > 170,
     "着地瞬间膝接近完全伸直,冲击较大,试着保持微屈(~160°)着地、脚落点在重心正下方"),
    ("pelvic_tilt_deg", lambda v: v is not None and abs(v) > 8,
     "骨盆侧倾较明显,提示髋外展稳定不足,可侧卧抬腿/蚌式加强臀中肌"),
]


def _fmt(v, unit=""):
    return f"{v}{unit}" if v is not None else "未测得(样本周期不足或该相位质量低)"


def _pace_line(metrics: dict):
    p = metrics.get("pace")
    if p:
        return (f"配速(估计): {p['pace_str']}/km ≈ {p['kmh']} km/h"
                f"(步长 {p['stride_m']}m,按身高 {p['height_cm']}cm 自标定,±20%级)")
    r = metrics.get("pace_reason")
    return f"配速: 未输出({r})" if r else None


def transparency_lines(result) -> list:
    """R-017v2 FR-8/9/10/12:透明度行——真实帧率/分析段/慢动作还原/配速口径。"""
    q, m = result.quality, result.metrics
    lines = []
    if q.get("fps_eff"):
        lines.append(f"分析帧率≈{q['fps_eff']}fps(PTS 实测)")
    if q.get("activity_span"):
        lines.append(f"跑动分析段 {q['activity_span']}s(站立/走位段已剔除)")
    if q.get("slo_factor", 1) > 1:
        lines.append(f"源为慢动作×{q['slo_factor']},步频已按倍速还原")
    if q.get("vfr"):
        lines.append("⚠容器为可变帧率,时间轴置信度降级")
    if result.crop_bbox:
        lines.append("骨架帧为关键区域裁剪版")
    pl = _pace_line(m)
    if pl:
        lines.append(pl)
    return lines


def summary_text(metrics: dict) -> str:
    lines = [
        f"步频 cadence_spm: {_fmt(metrics.get('cadence_spm'), ' 步/分')}",
        f"触地/腾空比 stance_swing_ratio: {_fmt(metrics.get('stance_swing_ratio'))}",
        f"着地瞬间膝角 knee_angle_at_contact_deg: {_fmt(metrics.get('knee_angle_at_contact_deg'), '°')}",
        f"蹬离瞬间膝角 knee_angle_at_toeoff_deg: {_fmt(metrics.get('knee_angle_at_toeoff_deg'), '°')}",
        f"髋屈伸活动度 hip_rom_deg: {_fmt(metrics.get('hip_rom_deg'), '°')}",
        f"骨盆侧倾 pelvic_tilt_deg: {_fmt(metrics.get('pelvic_tilt_deg'), '°')}",
        f"左右触地不对称度 asymmetry_pct: {_fmt(metrics.get('asymmetry_pct'), ' %')}",
    ]
    p = metrics.get("pace")
    if p:
        lines.append(f"估计配速 pace: {p['pace_str']}/km({p['kmh']} km/h,"
                     f"步长 {p['stride_m']}m,身高基准 {p['height_cm']}cm)")
    elif metrics.get("pace_reason"):
        lines.append(f"估计配速 pace: 未输出({metrics['pace_reason']})")
    return "\n".join(lines)


def template_report(result) -> str:
    m = result.metrics
    parts = ["📊 跑姿量化结果", "```", summary_text(m), "```", ""]
    hints = [txt for key, cond, txt in _RULE_HINTS if cond(m.get(key))]
    parts.append("💡 规则建议" + ("" if hints else "(各项指标在常见范围内)"))
    parts += [f"- {h}" for h in hints] or ["- 暂无突出风险项"]
    parts.append("\n(未启用视觉模型解读,以上为指标+规则报告;部署 VL 模型可获得教练式点评,详见 R-017)")
    tl = transparency_lines(result)
    if tl:
        parts.append("\nℹ️ " + "；".join(tl))
    parts.append("\n※ 数据基于单目视频估计,仅供参考,非医疗建议。")
    return "\n".join(parts)


def build_report(result, frame_b64s: List[str], *, llm=None, model: Optional[str] = None,
                 vision_ok=None) -> Tuple[str, str]:
    """→ (报告文本, 'vl'|'template')。永不抛出(AC-4 兜底)。

    frame_b64s:P4 读骨架帧转 base64(接口形态同 chat_service R-008 messages.images);
    llm/model/vision_ok 参数化仅测注入;默认真实 ollama_service/model_manager。
    """
    try:
        if llm is None:
            from core.llm import ollama_service as llm  # type: ignore
        if vision_ok is None:
            from core.model_manager import model_manager
            vision_ok = model_manager.supports_vision(model)
        if vision_ok and frame_b64s:
            tl = transparency_lines(result)
            ctx = summary_text(result.metrics) + ("\n(口径:" + "；".join(tl) + ")" if tl else "")
            msg = {"role": "user",
                   "content": "本次跑姿指标如下,请结合骨架帧出教练报告:\n" + ctx,
                   "images": list(frame_b64s)}
            from app.config import settings
            resp = llm.chat([{"role": "system", "content": SYSTEM}, msg],
                            temperature=0.4, model=model,
                            timeout=settings.POSE_REPORT_TIMEOUT)
            text = ((resp or {}).get("message") or {}).get("content", "")
            if text.strip():
                return text.strip() + "\n\n※ 数据基于单目视频估计,仅供参考,非医疗建议。", "vl"
            raise RuntimeError("VL 返回空内容")
    except Exception as e:
        log_event(logger, "pose.report", "vl", "fail", reason="vl_fail",
                  error=str(e)[:120])
    return template_report(result), "template"
