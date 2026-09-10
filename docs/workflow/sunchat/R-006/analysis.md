需求: R-006 | 代码分析

## A-1 热路径三处延迟放大点(micro 前置取证) — 2026-09-11
- 状态: confirmed | 用途:支撑 R-006/FR-1,FR-2,FR-3 根因
- 问题: 体检提案 P1/P2/R6 是否属实?重复调用/超时/缓存现状?
- 检索范围: services/chat_service.py, services/search_service.py, core/llm.py, core/memory_router.py, core/memory_extractor.py, core/model_manager.py, app/api/v1/routes/health.py, git log R-003

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | services/chat_service.py:273-277 | build_context 行情块 `stock_ctx = get_stock_context(content)` |
| 2 | [CODE] | services/chat_service.py:306 | 同请求内直查 miss 后 `search_svc.search_with_introduction(content, ...)`(content 相同) |
| 3 | [CODE] | services/search_service.py:47-52 | `search_with_introduction` 内部无条件再次 `get_stock_context(query)` |
| 4 | [CODE] | core/llm.py:21-22,125 | `_post` `timeout or settings.LLM_TIMEOUT`;generate 无 timeout 形参 |
| 5 | [CODE] | app/config.py:20 | `LLM_TIMEOUT: int = 300` |
| 6 | [CODE] | core/memory_router.py:87 / core/memory_extractor.py:60 | 轻分析/提取调用 `ollama_service.generate(prompt)` 走 300s 默认 |
| 7 | [GIT] | 2bf44d7f/0e9ba8e4 2026-09-08 R-003 | 仅给 DDG 探活加 `AVAIL_TTL=60` 缓存(core/search.py:21,75-83) |
| 8 | [CODE] | core/model_manager.py:113-120 | `is_available()` 每次 `requests.get(/api/tags, timeout=3)` 无缓存;/health 每请求调用(health.py:16 → llm.py:208-209) |
| 9 | [RUN] | TestClient GET /health 连发 2 次,mock tags 计数 | 桩未命中计数不可行→以 [CODE] 无缓存分支为准(单测 step-1 补 spy 断言) |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | 同一股价请求最坏路径行情 API 调用 2 次(chat 块 + search_with_introduction 内) | 1,2,3 |
| C2 | 记忆路由/提取轻调用占用 300s 默认超时,排队时阻塞热路径 | 4,5,6 |
| C3 | /health LLM 侧探活无缓存(R-003 只做了搜索侧同型问题) | 7,8 |

### 假设
- 无
