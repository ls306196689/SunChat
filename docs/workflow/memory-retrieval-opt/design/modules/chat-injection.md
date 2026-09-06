# M4 chat-injection

状态: draft r1 | 2026-09-06

## 1. 对外接口
- 无新增公有接口;改造 `services/chat_service.py`:
  - `build_context(...)`:`search_memories_by_analysis(..., top_k=settings.MEMORY_INJECT_TOPK)`(默认 5)
  - 注入片段仍为"用户背景信息"格式,但每条带最终分数标注,system prompt 文案不变
  - **删除死代码** `build_memory_context`(FR-2)
```
config 新增:
MEMORY_INJECT_TOPK: int = 5
```

## 2. 能力说明
- 提供:注入条目全部经过 M3 的阈值+重排+截断;死代码清除。
- 不提供:prompt 重写、记忆条目改写/摘要、注入位置调优。

## 3. 内部关键逻辑
- `analysis_result["user_input"]` 需在此处保证填充(memory_router 的 LLM 路径返回 `user_input:""`),M3 的原文优先策略依赖该字段——build_context 调用前 `analysis_result.setdefault("user_input", content)` 兜底填充。
- `_build_final_system_prompt` 中过滤逻辑交给 M3,本地不再做 0.3 阈值(已删死代码后唯一路径)。
- 日志:每次注入记 `[CHAT] 记忆注入 n条 top1_score=...`(可观测性约定)。

## 4. 依赖
- M3 `memory_service.search_memories_by_analysis`(design/modules/hybrid-search.md)
- 记忆提取路径(现有,不变):`memory_extractor` + `memory_service.update_or_create_memory`(M1 写入阈值在 memory_service/update_or_create 内生效,见 storage-consistency.md §3)
