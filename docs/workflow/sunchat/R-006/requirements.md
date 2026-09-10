需求: R-006 | 类型: iteration | 状态: 已确认 | 日期: 2026-09-11 | 版本: v1

# R-006 热路径延迟优化

## 1. 背景
全面体检(2026-09-10)发现对话热路径存在三处延迟/成本放大点(提案 B 组
P1/P2/R6,取证见 `analysis.md#A-1`)。R-003 已做行情直查短路+DDG 探活缓存,
本需求补齐剩余三点。

## 2. 与历史需求的关系
- 继承 R-003 短路语义(天气/行情命中不再走 DDG)不变;
- 修改 R-003 涉及的 `search_with_introduction` 调用面(仅增可选参数,合法行为不变);
- 与 R-004/R-005 契约面无交集。

## 3. 核心场景
- 用户问"XX 股价多少"且行情临时失败 → 现状:重复请求行情 2 次 + LLM 2 次全量生成;
  优化后:行情只取 1 次(复用已试结果),其余流程不变。
- Ollama 排队时用户发长句 → 现状:记忆路由 LLM 兜底最长阻塞 300s;优化后:
  轻调用 20s 超时快速回退规则结论。
- 容器编排 1s 轮询 /health 且 Ollama 无响应 → 现状:每次挂 3s×2 探测;优化后:
  LLM 探活结果缓存 30s(同 R-003 DDG 模式)。

## 4. 功能点
- FR-1 行情去重:`search_with_introduction` 接受已取行情上下文,chat 路径行情请求
  从最多 2 次降为 1 次;独立调用方(不传参)行为完全不变。
- FR-2 轻调用短超时:`ollama_service.generate` 支持 `timeout` 参数;
  memory_router 兜底分析与 memory_extractor 提取调用改走
  `LLM_LIGHT_TIMEOUT`(默认 20s),超时/失败按既有回退路径降级。
- FR-3 /health LLM 探活缓存:`model_manager.is_available` 结果缓存
  `HEALTH_AVAIL_TTL`(默认 30s),失败结果同样缓存;模型切换(set_*)时失效。

## 5. 边界与非目标
- 不改 SSE 帧协议、不改响应结构、不改 DDG 搜索与归纳逻辑本身;
- 搜索归纳 LLM 与主生成 LLM 的二次调用仅记录为后续候选(涉及回答质量权衡,
  本需求不动,见待澄清遗留项 D-202);
- 不引入新依赖。

## 6. 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | chat 行情失败路径 `get_stock_context` 仅被调用 1 次;成功短路路径不变 | spy 单测 |
| AC-2 | memory_router/memory_extractor generate 调用带 timeout=20;主对话 chat/generate 仍 300s | spy 单测(payload/timeout 断言) |
| AC-3 | `is_available` TTL 内多次调用底层 `requests.get` 仅 1 次;`set_chat_model` 后缓存失效可再测 | monkeypatch 单测 |
| AC-4 | /health 响应结构字段不变 | 契约断言(既有+新增) |
| AC-5 | 全量回归 | `pytest tests/` 全绿 |

## 7. 风险
| id | 风险 | prob | impact | 缓解 |
|---|---|---|---|---|
| R-1 | 轻调用 20s 误杀慢机器上的正常路由分析 | 低 | 中 | 失败走既有规则回退,行为降级不报错;超时可调 config |
| R-2 | is_available 缓存掩盖 Ollama 刚宕机(最多 30s 旧信息) | 低 | 低 | 与 R-003 DDG 缓存同语义先例;TTL 短 |
| R-3 | 行情去重改动破坏 search_with_introduction 独立调用方 | 低 | 中 | 参数可选、默认行为不变;既有 search 测试回归 |
