需求: R-013 | plan(标准 iteration;总授权直通)

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | trace 上下文 + evt 事件 + 聚合降噪 + uvicorn 日志治理(logger.py 核心)| utils/logger.py | R-013/{requirements,design-change,analysis}.md | logger.py(trace/TraceFilter/log_event/AggregatingFilter/setup_uvicorn_logging) | R-2,R-3 |
| 2 | 中间件 + 关键环节接线 + 堆栈补全 + 全量回归 + 实机 RUN | app/{middleware.py,main.py}, routes/{chat,speech,agent,knowledge}.py, services/chat_service.py, core/model_manager.py | 步骤1产出 + R-013/design-change.md | 代码 + tests/test_logging_system.py;验证:`pytest tests/test_logging_system.py -q`→`pytest tests/` 全绿 + 实机 curl 触发核对日志行 | R-1,R-4 |

> 单测硬门禁:步骤2含新增单测且全量回归绿。基线约束(FR-6)为文档规范,随归档写入
> design/modules/observability.md,代码类步骤已含测试。
