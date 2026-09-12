需求: R-013 | plan(标准 iteration;总授权直通)

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | trace 上下文 + evt 事件 + 聚合降噪 + uvicorn 日志治理(logger.py 核心)| utils/logger.py | R-013/{requirements,design-change,analysis}.md | logger.py(trace/TraceFilter/log_event/AggregatingFilter/setup_uvicorn_logging) | R-2,R-3 |
| 2 | 中间件 + 关键环节接线 + 堆栈补全 + 全量回归 + 实机 RUN | app/{middleware.py,main.py}, routes/{chat,speech,agent,knowledge}.py, services/chat_service.py, core/model_manager.py | 步骤1产出 + R-013/design-change.md | 代码 + tests/test_logging_system.py;验证:`pytest tests/test_logging_system.py -q`→`pytest tests/` 全绿 + 实机 curl 触发核对日志行 | R-1,R-4 |

> 单测硬门禁:步骤2含新增单测且全量回归绿。基线约束(FR-6)为文档规范,随归档写入
> design/modules/observability.md,代码类步骤已含测试。

## 验收总结(2026-09-12)

### AC 对照
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 trace 两级同码/异请求异码/后台继承 | 通过 | test_logging_system.py::TestTrace(route+http 行 `[r=trace]` 同码;`[x-request-id]` 透传/再生成;`copy_context` 线程继承断言;实机 r=live-test-9 贯穿 route/evt/http 行) |
| AC-2 环节事件 ok/fail+堆栈 | 通过 | TestEvents:upload/image 抽帧 bad_magic fail、speech ok(dur/text_len,不记文本)/fail reason=decode、log_event Traceback+竖线净化;实机 `evt=chat.message result=ok tokens=28` |
| AC-3 access 摘要+探活豁免 | 通过 | TestAccessSummary:普通请求恰 1 行 evt=http;health/OPTIONS 零行;4xx→WARNING;实机 grep 计数每请求 1 行、health 0 行 |
| AC-4 聚合降噪 | 通过 | TestAggregation:同模板 50→3 条(首条+repeat×20+×40);数字掩码归并;异模板隔离;INFO 全放行;evt 行 10/10 不聚合 |
| AC-5 失败堆栈可诊断 | 通过 | TestRoute500Stack evt=chat.message fail(exc_info);D-2 NameError 即由该堆栈当场定位;流式 error 帧回归(test_chat_router 全绿) |
| AC-6 全量回归+实机 RUN | 通过 | `pytest tests/` → 263 passed, 1 skipped;实机 8010/8011 隔离实例(真实 Ollama):chat/stream/400/health 日志样本核对,无轮转/gzip 回退(R-004 handler 未动,仅加 filter) |
| AC-7 SSE 零冗余 | 通过 | TestSSELogging:流式仅 1 条 evt=chat.stream done 行,delta/meta 零 info 计数锁死 |

### 全量单测摘要
`cd backend && pytest tests/ -q` → **263 passed, 1 skipped**(237→263:+25 logging+1 speech events,R-012 基线用例零回归)

### 风险终态
| R | 终态 | 说明 |
|---|---|---|
| R-1 日志量上升 | closed | 实机核对:普通请求 1 行摘要(非 uvicorn 全量 access),health 零行,轮转封顶不变 |
| R-2 丢 trace | closed | copy_context(chat_service)+generator 显式 set/resume(chat stream gen);AC-1 锁死 |
| R-3 聚合吞首见错误 | closed | 首条必放行+evt 永不聚合,单测断言 |
| R-4 既有测试冲突 | closed | 零断言冲突(只增文案),263 全绿 |

调试 D-1(ASGI 构造器)/D-2(NameError)/D-3(propagate 双写)全部 resolved,见 debug-log.md。
基线回写:design/modules/observability.md(新增)+ baseline.md 修订行 + overview.md 修订记录。
