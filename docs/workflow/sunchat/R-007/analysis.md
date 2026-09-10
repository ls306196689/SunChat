需求: R-007 | 代码分析

## A-1 资源与数据层加固点取证(需求前置) — 2026-09-11
- 状态: confirmed | 用途:支撑 R-007/FR-1,FR-2,FR-3 根因
- 问题: 体检提案 P5/R4/P3 是否属实?索引/线程/缓存现状与热查询路径?
- 检索范围: models/sql_models.py, services/chat_service.py, core/weather.py, core/stock.py, tests/test_weather.py, git blame 上述行

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | models/sql_models.py:237-343 | 9 张表全部仅 primary_key,无 index=True/Index |
| 2 | [CODE] | services/chat_service.py:47-49,64 | `Message.session_id == ... order_by(created_at).offset(...)` 与 `count()`——session_id+created_at 为最热查询面 |
| 3 | [GIT] | bc749ad7 2026-05-26 Initial commit;`git log -L 250,260:models/sql_models.py` | session_id 列自建库无索引,从未变更 |
| 4 | [CODE] | services/chat_service.py:405 | `t = threading.Thread(...daemon=True)` 每条消息裸起线程,[GIT] 2254f01a 引入;无池无上限 |
| 5 | [CODE] | core/weather.py:107-118 | `for city in _to_cities(query)` 串行 `requests.get(...,timeout=10)`,无缓存;`_to_cities` 上限 3 城→最坏 30s |
| 6 | [CODE] | core/stock.py get_stock_context | 每次直查 `_fetch_tencent(symbols)`,无缓存(对比 R-003 探活已缓 60s、R-006 is_available 缓 30s) |
| 7 | [REQ] | R-003/FR(探活缓存), R-006/FR-3 | 团队已确立"结果级 TTL 缓存、失败可缓存/不缓存"模式,本需求沿用 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | 热列(messages.session_id+created_at、chat_sessions.user_id、memories.user_id+is_active、kb_chunks.file_id、search_history.user_id)无索引,增长后全表扫描 | 1,2,3 |
| C2 | 记忆后台提取裸线程无上限,Ollama 慢时线程/连接无界增长 | 4 |
| C3 | 天气/行情直查无 TTL 缓存,重复追问重复外部请求,多城串行放大首延迟 | 5,6 |

### 假设
- 无
