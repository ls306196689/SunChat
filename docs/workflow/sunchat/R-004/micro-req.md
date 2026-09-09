# R-004 session_id 严格校验 + 日志轮转

需求: R-004 | 类型: bugfix+iteration(micro) | 状态: confirmed | 日期: 2026-09-09
> 门禁按用户总授权"直接执行"直通(2026-09-08),confirmed_by=user(delegated)。

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-09 | 初稿 | - |

## 一、需求
### 现象 / 动机
1. `POST /chat/messages` 与 `/chat/stream`:`session_id` 非数字时**静默回退会话 1**
   (`chat.py:67,210`),消息会串进错误会话;同文件 PATCH/DELETE(:158,:178)对非法 ID 一律
   400——同一资源校验语义不一致(`analysis.md#A-2` 观察项转修复)。
2. `utils/logger.py:29` FileHandler 无轮转,日志慢性增长(4.4M/约3月,`analysis.md#A-3`)。

### 期望行为
1. session_id 非法(非纯数字)统一 400 "session_id 非法";数字但不存在 → 维持现状
   (create_session 懒建,行为不变)。
2. 日志滚动:单文件 10MB × 保留 7 份;跨日仍按日新文件(行为兼容);logger 初始化时清理
   超过 30 天的历史日志文件(A-3 完整闭环)。

### 影响范围
- 文件: `backend/app/api/v1/routes/chat.py`, `backend/utils/logger.py`, `backend/tests/test_session_validation.py`(新增) — 3 文件
- 对外接口: 合法请求行为不变;仅非法输入由 200(串会话) 改 400(与 PATCH/DELETE 对齐)

### 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | 两聊天端点非法 session_id → 400 且 service 未被调用 | TestClient + monkeypatch spy |
| AC-2 | 合法数字 session_id 正常 200(回归) | 同上 |
| AC-3 | RotatingFileHandler:超过 maxBytes 滚动、保留≤7 备份 | 新增单测(小 maxBytes 触发轮转) |
| AC-4 | 全量回归 | `pytest tests/` 全绿 |

## 二、方案设计
### 改动点定位(附证据)
| 位置 | 证据 | 现行为 → 目标行为 |
|---|---|---|
| routes/chat.py:67 | `[CODE] int(...) if request.session_id.isdigit() else 1` | 非法→400(共用 `_resolve_session_id`) |
| routes/chat.py:210 | `[CODE] 同上模式` | 同上 |
| utils/logger.py:29 | `[CODE] FileHandler(LOG_FILE)` 无限增长 | RotatingFileHandler(maxBytes=10MB, backupCount=7) |

### 修改思路
新增模块级 `_resolve_session_id(raw)` 辅助(chat.py 内,非公开接口):isdigit 则 int,否则
raise HTTPException(400);两调用点替换(删除原 try/else-1 分支)。logger 仅换 handler
类型,路径/格式/级别不动;轮转文件命名 sunchat_YYYYMMDD.log.1~7。

### 回归测试设计
- 新增 test_session_validation.py:非法 "abc"/空串 → 400,monkeypatch process_message
  spy 断言未调用;合法(数字)→ spy 被调;logger 轮转用独立文件名+临时小 maxBytes 断言
  .1 备份产生且句柄仍可写。
- 既有 chat/security/agent 用例全量跑。

## 执行步骤(≤2)
| id | 目标 | 产出 + 验证方式 |
|---|---|---|
| 1 | 两路由 400 化 + logger 轮转 + 回归单测 | 验证: `pytest tests/test_session_validation.py -q && pytest tests/ -q` |

## 越界自检
- [x] ≤3 文件 [x] 合法请求接口行为不变 [x] 无新架构决策(标准库 logging) [x] 新依赖:无
