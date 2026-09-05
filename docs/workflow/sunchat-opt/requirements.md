# SunChat 优化(续)需求 — 冻结引用版

> 本需求为 `docs/优化方案/00~09`(2026-08-23 已由用户确认基线)的**续作**:
> 批次0地基已在代码中(未提交),本版收敛"剩余未完成项"。决策基线不变:
> SSE 流式+记忆异步+多轮;Agent 用 Ollama 原生 tool_calls 做成正式功能;认证=诚实单用户。

## 范围(G 对应 00-总览)
- G1 修断:KB 上传→处理→检索→引用 全链路;记忆列表 API;会话改名/删除
- G3 降本:记忆路由规则优先、提取异步、多轮上下文注入、去掉 system 双注入
- G4 正确性:search_knowledge where 过滤+content 取 documents、sqlite 回退变量遮蔽、
  冲突"以新为准"、Chroma 搜索 user_id 隔离、搜索接入对话
- G5 Agent:原生 tool_calls 重写 + 正式端点(mock LLM 可单测)
- G6 安全:删假 auth、接 sanitize_input、user_id 收敛 settings.LOCAL_USER_ID
- G7 治理:json_parser 落地复用、git 跟踪卫生(pycache/db 移出版本库)
- G8 门禁:全量 pytest 离线可跑全绿(mock LLM/embedding 网络调用)

## 非目标
- 多用户/真实 JWT、前端美观重设计、监控 Docker(K8s)——维持 Roadmap

## 验收标准
1. 上传 txt/md/pdf → 状态 processing→ready,`/kb/qa` 返回基于文档的 answer+sources;删除文件真实清理(SQLite+Chroma+磁盘)
2. `GET /memories` 返回真实分页列表,支持 type/category 过滤
3. `/chat/messages` 普通问候语 0 次路由 LLM 调用(mock 计数验证);带 search 走搜索归纳;system 仅注入一次;携带最近 N 轮历史
4. `POST /chat/stream` 返回 SSE 帧;前端流式渲染;改名/删除接通
5. 假 register/login 移除;chat/search/kb 输入过 sanitize
6. Agent 端点跑通 mock 工具循环;不可用时文本回退终止
7. `python -m pytest tests/ -q` 在无网络/无 Ollama 下全部通过
