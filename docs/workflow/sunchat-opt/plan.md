# sunchat-opt 执行计划

状态: 待确认 | 日期: 2026-09-05

## 步骤表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| S1 | 测试离线化守卫:conftest 增加 mock_llm/mock_embed fixture;test_process_message 等改用 mock,禁止真实网络 | tests | backend/tests/conftest.py, test_chat_service.py, test_search_service.py | 全量 `python -m pytest tests/ -q` <60s 全绿(无 Ollama 依赖用例) | R-1 |
| S2 | KB 管道修断:上传落盘(校验类型/大小)→BackgroundTasks 调 process_file;delete 路由接通 service;search_knowledge 传 where=user 过滤、content 取 documents、修 sqlite 遮蔽 bug | services/knowledge_service.py, core/document_parser.py 仅参考, routes/knowledge.py | 上述两文件 + tests/test_knowledge_service.py | 新增用例:upload→ready、where 隔离、delete 清理、sqlite 回退可用;`pytest tests/test_knowledge_service.py` | R-2 |
| S3 | 记忆修断:`GET /memories` 真实分页+过滤;update_or_create 冲突"以新为准"(更新 content 并重 embed);Chroma query 加 where user_id | services/memory_service.py, routes/memories.py | 上述 + tests/test_memory_service.py | 用例:列表返回真实数据、冲突更新内容、跨用户不可见;`pytest tests/test_memory_service.py tests/test_memories_api.py` | R-2 |
| S4 | 对话降本:memory_router 规则优先(关键词命中即免 LLM);process_message 去 system 双注入、注入最近 6 轮历史、search_enabled 时执行搜索归纳;memory_extractor 改后台线程异步;json 解析统一走 utils/json_parser | core/memory_router.py, services/chat_service.py, core/memory_extractor.py, utils/json_parser.py | 上述 + tests/test_chat_router.py | 用例:问候语 0 LLM 路由、system 单次、mock 计数=1 次生成、搜索路径拼接 sources;`pytest tests/test_chat_router.py tests/test_chat_service.py` | R-1,R-3 |
| S5 | SSE 流式:新端点 `POST /chat/stream`(存用户消息→流式转发→存 AI 消息→done 帧);前端 request.js 超时上调+新增 streamChat;chat store 流式渲染 | routes/chat.py, frontend/src/stores/chat.js, utils/request.js | 后端 chat.py+chat_service.py, 前端 chat.js/request.js/ChatView.vue | 后端 TestClient 读 SSE 帧用例;前端 `npm run build` 通过 | R-4 |
| S6 | 会话真操作:PATCH 改名、DELETE 软删实现(service+路由);前端调用接通 | services/chat_service.py, routes/chat.py, frontend stores | 同左 | 用例:改名后 list 变化、删除后 list 不含;`pytest tests/test_chat_service.py` | - |
| S7 | 认证诚实化:删假 register/login 端点仅留 whoami(或 501 语义);user_id=1 全部替换 settings.LOCAL_USER_ID;chat/search/kb 接入 sanitize_input(core/security.py) | routes/auth.py, 各 route, core/security.py | 上述 + config.py | 用例:假 token 端点移除、注入输入被拒、grep 无 user_id=1 硬编码;`pytest tests/` | R-5 |
| S8 | Agent 正式化:原生 tool_calls(Ollama /api/chat tools 参数)+解析失败文本回退;修 dataclass.get/role:tool 非法;新增 `/agent/run` 端点 | core/agent/*, 新 routes/agent.py, main.py | core/agent/agent.py,llm.py,tools.py,schema.py | mock LLM 多轮工具循环用例、回退终止用例,TestClient 打端点;`pytest tests/test_agent.py` | R-6 |
| S9 | 仓库卫生:git rm --cached pycache/db;全量测试终跑+更新 00-总览"执行结果"章节 | .gitignore, docs | 终态仓库 | `git ls-files | grep pycache` 为空;pytest 全绿摘要 | - |

## 豁免声明
- S9:纯 git/文档操作,单测由"全量测试终跑"承担验证。

## 依赖顺序图
S1 → (S2, S3, S4) → S5;S6 独立可并行;S4 → S7;S8 在 S4 后(复用 json_parser/llm);全部 → S9

## 提交约定
- 步骤完成: `feat(step-S<n>): <目标>`;批次0存量改动先 `chore(wip)` 存档

## 验收对照
| 需求验收项 | 覆盖步骤 |
|---|---|
| 1 KB 全链路 | S2 |
| 2 记忆列表/冲突 | S3 |
| 3 降本/多轮/搜索接入 | S4 |
| 4 SSE+前端+会话操作 | S5, S6 |
| 5 认证诚实+sanitize | S7 |
| 6 Agent | S8 |
| 7 测试门禁 | S1, S9 |
