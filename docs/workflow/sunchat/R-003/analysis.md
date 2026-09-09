# R-003 代码分析

## A-1 对话路径"直查族"(行情/天气)三重时序浪费 — 2026-09-08
- 状态: confirmed | 用途: 支撑 R-003/FR-1,2
- 问题: 行情与天气直查在同一条消息处理中有几处可避免的串行 HTTP 等待?
- 检索范围: backend/services/chat_service.py, search_service.py, core/{stock,weather}.py; backend/app/api/v1/routes/health.py

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | chat_service.py:270-297 | 行情直查先于天气直查,两段各自同步 requests,串行等待(天气最坏 10s×N 城市)。 |
| 2 | [CODE] | chat_service.py:270-301 | 行情命中后仅拼 system_prompt,decision 路由仍会走 search: `decision.get("tool")=="search"` → 天气命中才跳过路由,行情不置位(与天气不同源问题)→ 天气命中时若原问题也含行情词则行情数据注入后仍再走路由;行情命中但非天气时路由仍走(无行情跳过开关)。天气是唯一短路条件。 |
| 3 | [CODE] | health.py:17 + core/search.py:check_availability | `/health` 每次实时发 DDG test 搜索(`self.ddgs.text("test")`)。`[RUN] curl /health: 2.1s`,且前端健康面板若轮询将持续打 DDG。 |
| 4 | [GIT] | b243120a R-001 archive | 天气直查为最新引入;行情直查 d73a499f 早期引入,两者结构同构(意图词表+extract+format+失败None)。 |
| 5 | [DESIGN] | design/modules/chat-direct-weather.md §对外接口 | build_context 签名/返回结构不变。 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | 行情命中不会短路:天气命中→decision={"tool":None} 跳过路由;行情命中→仍进 route→search(行情数字注入 system + 搜索摘要也注入,双源冗余浪费一次 DDG) | 2 |
| C2 | 行情+天气可并行化(两段串行 HTTP,最坏相加);两模块同构,可用 ThreadPoolExecutor 并行两段且保留短路 | 1,4 |
| C3 | /health 的 search_available 每次阻塞真发网络请求 2.1s,前端轮询放大 DDG 限流风险 | 3 |

## A-2 会话 ID 回退脆弱与前端 URL 状态 — 2026-09-08
- 问题: session_id 异常输入的路径健壮性
- 检索范围: chat.py:205-210, stream_chat;agent.py:25-56

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | routes/chat.py:208-210 | `int(request.session_id) if request.session_id.isdigit() else 1` — 不合法直接静默 fallback 会话 1(用户消息会串会话) |
| 2 | [CODE] | agent.py 无 session 校验 | `chat.py` 已校验,agent 路由 session_id 仅 isdigit 判断,非数字丢弃无提示 |
| 3 | [CODE] | 前端 grep 未见 useSearchParams/URL | ⚠假设(证据不足):刷新页面/书签分享可能丢失会话。验证方法: 前端路由检查 |

## A-3 日志文件无限增长 — 2026-09-08
### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [RUN] | du -sh backend/logs → 4.4M; ls 见 sunchat_YYYYMMDD.log 按日分文件 | 无轮转清理策略,长期累积 |

### 结论
| C1 | 日志按日分文件但无 rotation/保留上限,磁盘慢性增长(低危,非阻塞) |
| A-2/3 立题状态: A-1 直接支撑本需求改动;A-2 为观察项(未修,记基线备注);A-3 为观察项。
