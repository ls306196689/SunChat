需求: R-013 | debug-log | 调试记录(实现验证期发现,均已解决)

## D-1 纯 ASGI 中间件缺构造器(2026-09-12,step-2 前置验证)
- 复现:`pytest tests/` 全量回归 62 failed,`TypeError: RequestLogMiddleware() takes no arguments`
  (`app = cls(app=app)` Starlette 装配方式)。
- 假设/证据:中间件仿 Starlette 纯 ASGI 规范写但未定义 `__init__(app)`;[CODE] 装配栈证据直接。
- 修复:补 `def __init__(self, app): self.app = app`。回归:237 全绿。
- 状态:resolved。

## D-2 create_message 内 session_id 未定义(2026-09-12,新增单测抓出)
- 复现:`tests/test_logging_system.py::test_route_and_http_share_trace` → 500,
  `NameError: name 'session_id' is not defined`(chat.py:245 evt 行)。
- 假设/证据:原代码 session_id 内联于 `_resolve_session_id(request.session_id)` 实参,
  无局部变量;接线 evt 时引用了不存在的名字。[CODE] traceback。
- 修复:提取局部变量 `sid`,evt 与传参共用。回归:该测通过+全量 262 绿。
- 附加价值:该 evt fail 路径带 exc_info 当场暴露堆栈,正是 R-013 要的能力。

## D-3 子 logger 事件沿 propagate 双写(2026-09-12,实机 RUN 抓出)
- 复现:实机 8010 端口 RUN,`evt=http` 行在 sunchat_*.log 成对重复。
- 假设/证据:`sunchat.http` 是 `sunchat` 子 logger;get_logger 为其挂自有 handler 后
  仍向父传播,父 handler 再写一次。[RUN] 日志成对样本+[CODE] logging 传播语义。
- 修复:get_logger 对含 "." 的名字置 `propagate=False`。回归:实机 8011 RUN 每请求
  1 行、/health 零行;全量 262 绿。
