需求: R-013 | 类型: iteration | 状态: v1 已授权 | 日期: 2026-09-11 | 版本: v1

# R-013 日志体系完善(请求关联 + 关键环节全覆盖 + 高频降噪)

## 1. 背景
用户指令(2026-09-11):业务流程每个关键环节都要有日志检测、不管成功失败,方便问题
排查;针对高频场景特别设计避免无效日志淹没有效信息(analysis A-1/6)。体检确认
三缺口(A-1/C1-C3):无请求级关联、多模态/工具关键环节空窗、已知噪声源未治理。
R-012 排查实况印证:业务日志与 uvicorn access 分流且无关联 ID,人工时间戳对齐费时。

## 2. 与历史需求的关系
- 延续 R-004(日志轮转/30天清理)的 utils/logger.py 基座,不回退其能力;
- 不改变任何端点响应契约(纯观测面);既有 logger.info "文案" 兼容保留(只增不改)。

## 3. 核心场景
1. 排错串查:一次对话(含图/帧/语音)在日志中凭 `trace=<6位码>` 把
   上传→路由→LLM→落库→(SSE) 全链路串起;失败堆栈完整可查。
2. 关键环节成败可查:上传/抽帧/转写/对话/搜索/KB/agent/记忆 均输出
   `evt=<域.动作> result=ok|fail` 事件行(成功失败皆记)。
3. 降噪:探活轮询(access+is_available)不逐条记录;同模板重复告警按周期聚合
   (首条全量,后续 N 次聚合成 1 条摘要);外部依赖失败降级 DEBUG 级带聚合。
4. 单文件可诊断:sunchat_*.log 同时含访问事件(摘要级)与业务事件,trace 互串。

## 4. 功能点
- FR-1 trace 上下文:request_id contextvar + LoggingFilter 注入 `[r=xxxxxx]`;
  HTTP 入口(HTTP 中间件)生成/透传 `X-Request-ID`;SSE generator、后台线程池
  任务(copy_context)继承 trace。
- FR-2 环节事件:统一 `log_event(domain, action, result, **fields)` 工具;接入
  关键环节:chat.messages/stream、chat.image.upload、chat.video.frames、
  speech.transcribe、agent.run、search、kb.upload/process、memory.extract、
  storage.reconcile——成功失败都记,fail 必带 exc_info。
- FR-3 访问摘要:进程内 ASGI 中间件把请求完成写为业务日志一行
  `evt=http method path status ms`(非2xx 为 WARNING),替代 stdout access 噪声;
  uvicorn access 关闭;/health 与 OPTIONS 不记(探活)。
- FR-4 高频降噪:`AggregatingFilter` 按模板(key=level+首60字符去数字)聚合:
  首条即时,窗口(60s)内重复计数,窗口外输出一条 `repeat×N`;
  model_manager.is_available 失败日志降为聚合计数;chat/stream 的 heartbeat/
  delta 零日志(现状已无,补测试锁死)。
- FR-5 失败堆栈:routes 500 分支 `logger.error(..., exc_info=True)`(chat/agent/
  memories/search/knowledge)。
- FR-6(规范约束,写入 design 基线):后续新需求涉及业务流程必须在方案文档含
  "日志设计"节;环节清单=需求验收项。

## 5. 边界与非目标
- 不引入第三方日志框架(loguru/structlog 免依赖);不做集中式采集/ELK(本地单用户);
- JSON Lines 双轨文件留候选(本期单文件文本,trace 可 grep);
- uvicorn 启动 INFO 保留(一次性非噪声);前端 console 日志体系不在本期(候选 R-014)。

## 6. 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | trace:同请求内 route/service 两级日志含相同 `[r=`;不同请求 trace 不同;后台提取线程继承 | 单测 caplog |
| AC-2 | 事件行:上传成功与失败各有 `evt=chat.image.upload result=ok|fail`;失败带堆栈;speech/video/chat 同样断言 | 单测 |
| AC-3 | access 摘要:普通请求一行 evt=http;`/health` 与 OPTIONS **不产生日志** | 单测 |
| AC-4 | 聚合降噪:同模板错误 50 条→首条+聚合行(总条数显著下降,计数正确);异模板不互相聚合 | 单测 |
| AC-5 | LLM 失败可诊断:失败路径 error 含堆栈(exc_info);流式 error 帧行为回归 | 单测+回归 |
| AC-6 | 全量回归:pytest 全绿;实机 RUN:gzip/轮转不受新 handler 影响、真实 /health+chat 日志样本核对 | 实机 |
| AC-7 | SSE 流式路径零 delta/meta 冗余 info(仅 done 一条 evt 行) | 单测 |

## 7. 风险
| id | 风险 | prob | impact | 缓解 |
|---|---|---|---|---|
| R-1 | 中间件每请求多写一行,高频下日志量上升 | 中 | 低 | /health+OPTIONS 豁免(access摘要100字内);轮转封顶仍在 |
| R-2 | contextvar 在 stream/线程池丢 trace | 中 | 中 | copy_context 包裹(标准模式),AC-1 锁死 |
| R-3 | 聚合误伤首见错误被计数吞掉 | 低 | 中 | 模板首现必全量;60s 窗口;仅 ERROR/WARN+重复模板生效 |
| R-4 | 既有测试断言日志文案冲突 | 低 | 低 | 零删除只增补;全量回归发现即修正并注明 R-013 |
