# sunchat 需求台账

当前需求 ID:R-009(下一个将分配;R-008~R-010 为多模态三期规划:图片/语音/视频) |
设计基线:见 baseline.md

## 需求历史
| ID | 主题 | 类型 | 状态 | 基线修订 | 起止日期 |
|---|---|---|---|---|---|
| (预流程) | sunchat-opt 系统优化收敛(S1-S9) | feature | done | - | 2026-09-05~06 |
| (预流程) | memory-retrieval-opt 记忆检索优化 | iteration | done | 产出 design/ 基线 | 2026-09-06 |
- 预流程两条为 req-dev 引入前的旧工件,原位保留于
  `docs/workflow/sunchat-opt/`、`docs/workflow/memory-retrieval-opt/`(只读归档,追溯编号经
  用户确认豁免,2026-09-08)。
- 本台账自 R-001 起执行 R-NNN 主线;commit 必须含 R-NNN。

| R-001 | 天气直查(wttr.in 数据源+对话直查+Agent get_weather 工具) | feature | done | weather-core/chat-direct-weather | 2026-09-08 |
| R-002 | Agent 工具框架 user_id 注入缺陷修复 | bugfix | done | - | 2026-09-08 |
| R-003 | 直查短路补全(行情)+/health 探活缓存 | iteration | done | - | 2026-09-08 |
| R-004 | session_id 统一400校验+日志轮转与30天清理 | bugfix | done | - | 2026-09-09~10 |
| R-005 | session 契约收口(GET 400+分页限幅+Agent 非法 id 400+死文件清理) | bugfix | done | - | 2026-09-11 |
| R-006 | 热路径延迟优化(去重复 LLM/行情调用+轻调用短超时+/health 缓存) | iteration | done | - | 2026-09-11 |
| R-007 | 资源与数据层加固(DB 索引+记忆提取线程池+天气/行情 TTL 缓存) | iteration | done | - | 2026-09-11 |
| R-008 | 对话图片输入(多模态 V1:图片问答+存盘+历史回显) | iteration | done | chat-image(新增) | 2026-09-11 |
