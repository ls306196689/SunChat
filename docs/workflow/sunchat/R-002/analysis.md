# R-002 代码分析

## A-1 Agent 工具框架 user_id 无条件注入导致无该形参的工具必然失败 — 2026-09-08
- 状态: confirmed | 用途:支撑 R-002 根因
- 问题: Agent function-calling 路径下 web_search 为何执行失败(用户最初报"天气查询失败"的成因之一)?
- 检索范围: backend/core/agent/tools.py(HEAD 工作区+修改前), git log -S, 日志 backend/logs/sunchat_20260908.log

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | 修改前 `git show HEAD:backend/core/agent/tools.py`:152 | `args["user_id"] = user_id or settings.LOCAL_USER_ID` 无条件注入 |
| 2 | [CODE] | 同上:154-155 | `allowed = properties.keys() | {"user_id"}`,user_id 恒被放行 |
| 3 | [CODE] | HEAD tools.py `web_search(query, max_results=5)` 签名 | 无 user_id 形参 |
| 4 | [RUN] | 本会话验证:`execute_tool('web_search', {'query':'test'})` | `web_search() got an unexpected keyword argument 'user_id'`,success=False |
| 5 | [GIT] | d73a499f 2026-09-05 feat(step-S8) "user_id强制注入防越权" | 该机制引入时只考虑了带 user_id 的记忆类工具 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | execute_tool 对所有工具无条件注入 user_id,签名不含 user_id 的 web_search 在 Agent 路径 100% 抛 TypeError | 1,2,3,4 |
| C2 | 根因属 S8 设计疏漏:防越权注入未区分"工具是否接受 user_id" | 5 |

### 假设(无证据,不得作为改动依据)
- 无

### 矛盾归因(如有)
- commit message "防越权"(安全目标) vs 实现缺陷(越权防护有效但破坏合法工具) → 实现违约 @d73a499f,由本次修复消除
