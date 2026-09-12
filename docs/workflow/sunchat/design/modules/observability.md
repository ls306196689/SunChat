需求: R-013 | 设计基线模块(横切:observability)| 版本: v1 (R-013 归档回写 2026-09-12)

# observability 日志体系(横切)

## 对外接口(utils/logger.py,零第三方依赖)
- `get_logger(name='sunchat')`:带轮转(R-004:10MB×7+30天清理)、五段格式
  `时间 | 级别 | [r=trace] | logger名 | 消息` 的统一 logger;含 "." 的子名
  自动 `propagate=False`(防双写,R-013/D-3)。
- trace 上下文:`new_trace()`(6位hex)/`set_trace(v)→token`/`reset_trace(token)`/
  `get_trace()`;`TraceFilter` 为 record 注入 `trace` 字段。
- `log_event(log, domain, action, result, exc=False, level=None, **fields)`:
  关键环节事件行 `evt=<domain>.<action> result=<ok|fail|skip> k=v…`;fail→ERROR
  (可 exc=True 带堆栈),level 可覆盖(http 4xx→WARNING);字段净化(竖线/换行,
  ≤120字符);extra no_agg 永不参与聚合。
- `AggregatingFilter`(文件+控制台 handler 共享):WARNING+ 非 no_agg 记录按
  `级别+数字掩码前72字符` 模板聚合,首条必放行,每满 AGG_THRESHOLD=20 放出一条
  `(repeat×N)` 摘要。
- `setup_uvicorn_logging()`:uvicorn.access 静默(level=WARNING,自有摘要替代),
  httpx/httpcore/urllib3/chromadb 等三方库 INFO→WARNING;幂等。

## app/middleware.py::RequestLogMiddleware(纯 ASGI)
- 非 `/health`、非 OPTIONS:`X-Request-ID` 合法透传(否则 new_trace),响应头回传;
  完成(或异常)时一行 `evt=http method result=ok|fail path status ms`;
  ≥500 ERROR fail、4xx WARNING ok(业务拒绝非服务故障)、SSE 于 response start
  记录(ms≈TTFB,D-704);finally reset trace。

## 日志设计规范(基线约束,后续需求方案必含"日志设计"节)
1. 关键环节一律 `log_event(...)`;成功失败必记,fail 带 exc_info;环节清单进需求验收。
2. 域清单(基线):http / chat / chat.image / chat.video / speech / agent / search /
   kb / memory / storage / model。
3. 高频约束:探活(`GET /health`、OPTIONS)不记;delta/meta/轮询零日志;自由文案
   告警走阈值聚合(N=20);`evt=` 行永不聚合。
4. 外部探活降级:`model_manager.is_available` 边沿翻转才 info 一条,其余 debug。

## 已接线环节(接线图)
- `main.py`:create_app 挂 RequestLogMiddleware + setup_uvicorn_logging;
  lifespan 存储对账 `evt=storage.reconcile`。
- `routes/chat.py`:`evt=chat.image.upload` / `chat.video.frames` / `chat.message`
  (ok+fail 全分支)/ `chat.stream`(done 一条,fail 带堆栈;delta/meta 零日志)。
- `routes/speech.py`:`evt=speech.transcribe`(ok 含 dur/text_len,不记转写文本)。
- `routes/agent.py`:`evt=agent.run`(ok 含 mode/iterations/tools)。
- `routes/knowledge.py`:`evt=kb.upload`(拒绝原因 reason=bad_type/oversize)。
- `routes/search.py`:`evt=search.query`。
- `services/chat_service.py`:extract_memories_async 以 `contextvars.copy_context()
  .run` 提交线程任务(trace 继承,AC-1);apply_memory_extraction 输出
  `evt=memory.extract`(ok saved=n / fail 带堆栈)。
- `core/model_manager.py`:is_available 边沿翻转 `evt=model.availability`。
- `routes/memories.py`:500 分支 `exc_info=True` 堆栈补全。

## 测试约定
`tests/test_logging_system.py`(25 用例,对应 AC-1~5/7):trace 注入/继承/
透传/再生成;evt ok/fail+堆栈+净化;http 摘要行/探活豁免/级别;聚合首条+计数+
异模板隔离+evt 豁免;SSE 仅 done 一条 evt 行。新增环节须带对应断言。

## 决策(D-701~704,见 R-013/design-change.md)
单文件文本+trace 前缀不上 JSON;阈值计数聚合非时间窗;access 摘要进业务日志;
SSE http 摘要 ms=TTFB。
