# R-004 代码分析

## A-1 session_id 校验语义不一致(消息串会话风险) — 2026-09-09
- 状态: confirmed | 用途: R-004/FR-1
- 检索范围: backend/app/api/v1/routes/chat.py, frontend/src/stores/chat.js

### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | routes/chat.py:67 | `int(request.session_id) if request.session_id.isdigit() else 1`(POST /chat/messages) |
| 2 | [CODE] | routes/chat.py:210 | 同模式 `else 1`(/chat/stream) |
| 3 | [CODE] | routes/chat.py:158,178 | PATCH/DELETE:`except ValueError: raise HTTPException(400, "session_id 非法")` — 同资源不同语义 |
| 4 | [RUN] | `grep session_id frontend/src/stores/chat.js:158` → 前端 total 3 处均为真实 session 对象取值 | 前端正常路径永远发数字,400 化对现有 UI 零影响 |

### 结论
| # | 结论 | 依赖证据# |
|---|---|---|
| C1 | 非数字 session_id 会静默写入会话 1;与 PATCH/DELETE 的 400 语义冲突,统一为 400 风险可控 | 1,2,3,4 |

## A-2 日志无限增长 — 2026-09-09
### 证据
| # | 标签 | 出处 | 摘录/摘要 |
|---|---|---|---|
| 1 | [CODE] | utils/logger.py:15,29 | `LOG_FILE=sunchat_%Y%m%d.log` + `logging.FileHandler(...)` 无轮转 |
| 2 | [RUN] | du -sh backend/logs → 4.4M(2026-06-07 起) | 慢性增长,低危高确定 |

### 结论
| C1 | 按日分文件但单文件无上限;RotatingFileHandler(10MB×7)封顶 | 依赖 1,2 |
