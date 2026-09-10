需求: R-006 | 类型: iteration | 状态: 已确认 | 日期: 2026-09-11

# R-006 增量设计(design-change)

相对基线 `design/`:不改任何在册模块对外接口签名,仅在热路径调用面做去重/超时/缓存
三类局部改动(与 R-003"直查短路+探活缓存"同型)。

## 改动 1:行情上下文去重(FR-1)
- `services/search_service.py:search_with_introduction(query, memories, max_results)`
  → 增可选参数 `stock_context=_UNSET`(模块级哨兵)。`_UNSET` 时维持现状自取;
  显式传入(含 None)时直接使用、不再自取 [DESIGN: analysis.md#A-1 C1]。
- `services/chat_service.py` build_context 行情块:保存 `stock_ctx`(成功/失败均有值),
  调 `search_with_introduction(content, memory_context, stock_context=stock_ctx)`。
  命中短路(stock_hit)路径不增调用。

## 改动 2:轻调用短超时(FR-2)
- `core/llm.py:generate(...)` 增 `timeout: Optional[int] = None` 透传 `_post`
  (None → 默认 `LLM_TIMEOUT` 300s,主对话/chat 路径不变)。`generate_detailed` 暂不加
  (无轻调用方,避免无验证代码)。
- `core/memory_router.py:87` 与 `core/memory_extractor.py:60` 的 generate 调用传
  `timeout=settings.LLM_LIGHT_TIMEOUT`。失败路径既有回退(规则结论/空提取)不变。
- `app/config.py` 新增 `LLM_LIGHT_TIMEOUT: int = 20`。

## 改动 3:/health LLM 探活缓存(FR-3)
- `app/config.py` 新增 `HEALTH_AVAIL_TTL: int = 30`。
- `core/model_manager.py`:`is_available()` 结果缓存 `(monotonic_ts, bool)`,失败同样缓存
  (同 R-003 `search.AVAIL_TTL` 语义 [REQ: R-003/FR]);新增 `invalidate_availability_cache()`,
  `set_chat_model/set_embedding_model` 内调用(与现有 `_available_cache = None` 并列)。

## 不改清单
- SSE 协议、chat 响应结构、DDG 搜索与归纳 prompt、健康检查响应字段、
  search_with_introduction 独立调用默认行为。

## 风险表(与 state.risks 同步)
| id | 风险 | prob | impact | 缓解 |
|---|---|---|---|---|
| R-1 | 轻调用 20s 误杀慢机器路由分析 | 低 | 中 | 回退规则结论不报错;config 可调 |
| R-2 | is_available 缓存 30s 旧信息 | 低 | 低 | R-003 DDG 同语义先例;set_* 失效 |
| R-3 | 去重破坏 search_with_introduction 既有调用方 | 低 | 中 | 哨兵默认=原行为;回归既有 search 测试 |

## 决策
- [D-201] 2026-09-11 哨兵参数而非 `Optional[str]=None`:None 本身是合法值("已试且失败"),
  必须与"未试"区分。
- [D-202] 2026-09-11 搜索归纳 LLM 二次生成暂不合并:涉及回答质量(归纳摘要 vs 全文生成)权衡,
  留作后续需求候选,本需求不引入回答质量回归风险。
