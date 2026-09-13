# 模块设计:pose-report(core/pose_report.py)

需求: R-017 | 触发: FR-5 (决策 D-002) | 日期: 2026-09-13 | 状态: draft r1

## 对外接口
```python
def build_report(result: PoseResult, frame_ids: list[str],
                 *, llm=None, model: str = None) -> tuple[str, str]:
    """指标+骨架帧 → (报告文本, 来源标记 'vl'|'template')。
    frame_ids 为 P4 已落盘的骨架帧 id(用于 chat images 与提示词引用)。
    llm/model 参数化仅为单测注入(默认真实单例)。"""

def template_report(result: PoseResult) -> str:
    """降级模板报告:指标表 + 规则建议。无 LLM 依赖,纯确定性。"""
```

## 能力说明
- 提供:VL 与模板双路报告文本;来源标记供落库/日志(AC-4 验证)。
- 不提供:消息存盘(P4)、模型可用性管理(读 model_manager 既有 `supports_vision()`)。

## 内部关键逻辑
1. **探测**:`model_manager.supports_vision(model)` 为 False → 直接 template_report;
   True → 组消息:`{"role":"user","content":指标摘要+诉求, "images":[b64,...]}`(b64 由
   P4 读落盘帧转换注入,P3 只收现成列表——同 chat_service R-008 消息内嵌 images 形态),
   system 规定输出结构:三段式(量化指标解读/左右对比与风险/改进建议 3~5 条),温度 0.4。
2. **降级**:Ollama 超时/异常(LLMException)→ 捕获 → template_report,`evt=pose.report
   result=fail reason=vl_fail` 后仍出报告(result ok 但 report=template)。
3. **模板规则**(确定性):不对称度>10% → "左右腿差异较大,建议关注弱侧/排查旧伤";
   cadence<160 → "步频偏低,可尝试提高步频减小跨步";触腾比>2.5 → "触地偏长,注意蹬伸
   发力";每条附"仅供参考,非医疗建议"。
4. 指标摘要文本逐键:无则"未测得(样本周期不足或该相位质量低)"。

## 依赖
- P1:`PoseResult`(接口名)。
- 既有:`core.llm.chat(messages, images=..., model=...)`、
  `core.model_manager.<mgr>.supports_vision()`(R-008 已定义消费面,本模块只读)。
