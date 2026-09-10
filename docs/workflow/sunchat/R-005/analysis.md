# R-005 代码分析

## A-1 session 契约在 GET/agent 端点未收口 — 2026-09-10
- 状态: draft | 用途:支撑 R-005 需求根因(micro bugfix 前置)
- 问题: R-004 确立的"非法 session_id 一律 400、禁止静默降级"契约是否覆盖 GET 消息端点与 Agent 端点?分页参数有无校验?
- 检索范围: backend/app/api/v1/routes/chat.py, routes/agent.py, tests/test_session_validation.py, frontend/src(grep session_id), git blame/log 上述文件

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [REQ] | R-004/micro-req.md §期望行为 | "session_id 非法(非纯数字)统一 400 'session_id 非法'…数字但不存在→维持现状" |
| 2 | [GIT] | 4e005fa8 2026-09-09 fix(R-004/step-1) | 仅改 POST /chat/messages 与 /chat/stream 两端点(引入 `_resolve_session_id`),GET 端点不在改动内 |
| 3 | [CODE] | backend/app/api/v1/routes/chat.py:137-144 | `def get_messages(session_id: str, page: int = 1, page_size: int = 20)` 直接 `int(session_id)`,无 `_resolve_session_id` 守卫、无 except |
| 4 | [CODE] | backend/app/api/v1/routes/chat.py:27-31 | `_resolve_session_id` 已存在("R-004: …非法一律 400"),PATCH/DELETE(:156,:176)经 except ValueError 已有 400 |
| 5 | [CODE] | backend/app/api/v1/routes/agent.py:36-38 | `if request.session_id and request.session_id.isdigit():` 非数字时静默跳过 history 加载与落库 |
| 6 | [GIT] | d73a499f 2026-09-05 feat(step-S8) | agent 端点引入时即为 `.isdigit()` 静默式(S6 期 chat.py 同款模式,R-004 只收口了 chat 侧) |
| 7 | [RUN] | TestClient 复现: `GET /api/v1/chat/sessions/abc/messages` | → 500(未捕获 ValueError),期望契约应 400 |
| 8 | [RUN] | TestClient: `GET /api/v1/chat/sessions/1/messages?page=0` | → 200,chat_service 收到 page=0 → offset=-20(SQLite 负 offset 容忍,分页语义错误);page_size 无上限 |
| 9 | [RUN] | TestClient: `POST /api/v1/chat/agent` {"session_id":"abc"} + spy | → 200 且 save_user_message 未被调用——对话"成功"但历史静默丢失 |
| 10 | [CODE] | backend/tests/test_session_validation.py:34-66 | 仅覆盖 POST/stream 非法 id;GET/agent/分页零用例 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | GET /chat/sessions/{id}/messages 非法 id → 500,违反 R-004 已确立的 400 契约 | 1,2,3,7 |
| C2 | 分页参数无校验:page<1 产生负 offset 且返回 200,page_size 无上限 | 8 |
| C3 | Agent 端点非空非法 session_id 静默降级(200 但不落库),与 R-004"禁止静默降级"相悖;空 session_id 无会话模式为既有合法语义应保留 | 1,5,6,9 |
| C4 | 既有测试盲区恰在本契约面:GET/agent/分页无用例,修复须先补 red test | 10 |

### 假设(无证据,不得作为改动依据)
- 无

### 矛盾归因
- R-004 契约(400)vs GET/agent 实现(500/静默)→ 实现违约(R-004 治理范围当时只声明"两聊天端点",同型端点未覆盖,非文档过时)
