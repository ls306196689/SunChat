需求: R-013 | 增量设计 | 状态: v1 | 日期: 2026-09-11

# design-change(横切:observability;归档回写 design/modules/observability.md)

## 日志设计规范(基线约束,后续需求"日志设计"节依此执行)
1. 关键环节一律走 `log_event(domain, action, result, ...)` →
   `[r=<trace>] <LEVEL> | <logger> | evt=<domain>.<action> result=<ok|fail|skip> k=v…`;
   成功失败必记,fail 带 `exc_info=True`;环节清单进需求验收。
2. 域清单(基线):http / chat / chat.image / chat.video / speech / agent / search /
   kb / memory / storage / asr / model。
3. 高频约束:探活(`GET /health`、OPTIONS)不记;delta/meta/轮询零日志;
   自由文案告警走阈值聚合(首条即时,每满 N=20 重复输出一条 `repeat×N` 摘要);
   `evt=` 事件行永不聚合(no_agg 标记)。
4. 外部探活降级:is_available/check_availability 类布尔探测失败→debug+聚合,
   仅"翻转时刻"(true→false / false→true)info 一条。

## utils/logger.py(核心,零新依赖)
- `_trace_var: ContextVar[str]("-")`;`new_trace()`(uuid4 hex 6 位);
  `set_trace/get_trace`;`TraceFilter` 注入 `record.trace`。
- `LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(trace)s | %(name)s | %(message)s'`
  (旧 4 段→5 段,兼容 grep `[r=`)。
- `log_event(logger, domain, action, result, **fields)`:拼 `evt=… result=… k=v`;
  fail→error(exc_info 由调用方 except 上下文,extra no_agg+trace 沿用当前 ctx)。
- `AggregatingFilter`(挂 file+console handler):key=f"{levelno}|{digits_mask(msg)[:72]}";
  仅 WARNING+ 且非 no_agg;count 每满 AGG_WINDOW_N=20 → 放行改写为
  `原消息 (repeat×20 within window)` 并清零;未达阈值抑制。数字掩码使
  "attempt 1/2/3"、计数变化归并同模板。
- `setup_uvicorn_logging()`:`uvicorn.access` logger 置 level=WARNING(自有摘要接管);
  `uvicorn.error` 保持。

## app/middleware.py(新增,纯 ASGI)
- `RequestLogMiddleware`:非 `/health`/非 OPTIONS → trace=new_trace()(透传合法
  `X-Request-ID` `^[A-Za-z0-9-]{1,32}$`),set_trace;wrap send 取 status;完成时
  `evt=http result=ok|fail method path status ms`(>=400→WARNING,含 4xx 业务拒绝;
  5xx fail);finally reset token。SSE 长流:响应头发出即计 done(记 response_start,
  流结束不可靠→以 header send 时刻为准,ms≈TTFB,注记语义)。

## 接线(最小侵入)
- `app/main.py`:setup_uvicorn_logging() + add_middleware;
- `routes/chat.py`:上传/抽帧/非流/流(开始+done+error 帧各一 evt,done 于 finalize 后)
  +500 分支 exc_info;`routes/speech.py`:转写 ok(含 dur/text_len,不记文本)/fail+500;
  `routes/agent.py`:run 完成/失败 evt;`routes/knowledge.py`:上传拒绝/成功 evt+500 exc_info;
  `services/chat_service.py`:extract_memories_async 以 `contextvars.copy_context().run`
  包装线程任务(继承 trace);apply_memory_extraction 已有 memory_logger →
  增 `evt=memory.extract result=` 收尾事件;process_message/stream 失败路径 error+exc_info。
- `core/model_manager.py`:is_available 状态翻转 info 一条,其余失败 debug(聚合)。

## 测试(tests/test_logging_system.py)
- trace:caplog 断两 handler 行含 `[r=`;中间件注入/透传/health 豁免;不同请求异 trace。
- evt:上传 ok/fail 两行断言 result=;fail 含 Traceback。
- 聚合:同模板 warning×50 → 文件 handler 中 1 首条 + 2 聚合计数行;evt 行不受聚合。
- SSE:流式 mock 下无 delta/meta info(计数锁死)。
- 回归:全量 pytest。

## 决策
- [D-701] 单文件文本+trace 前缀(可 grep),不上 JSON Lines/第三方框架——本机单用户,
  与现有 grep 习惯/R-004 轮转兼容;JSON 双轨留后续候选。
- [D-702] 聚合用"阈值计数"而非时间窗:无后台线程无递归风险,确定性强;"不管成功失败
  都要有记录"的底线由 evt 事件行保证(永不聚合)。
- [D-703] access 摘要在业务日志内(自有中间件),关闭 uvicorn.access:单文件可串,
  消除双文件人工对齐(R-012 痛点)。
- [D-704] SSE 的 http 摘要 ms=TTFB(header 时刻),完整流式时长已由 chat done evt 行覆盖。
