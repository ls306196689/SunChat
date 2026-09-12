"""
SunChat Backend - 请求日志中间件 (R-013)
trace 注入 + 访问摘要(evt=http)进业务日志,替代 uvicorn.access。
健康检查与 OPTIONS 预检不记(探活噪声)。
"""
import logging
import re
import time

from utils.logger import get_logger, log_event, new_trace, reset_trace, set_trace

_logger = get_logger("sunchat.http")
_VALID_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,31}$")


class RequestLogMiddleware:
    """纯 ASGI:生成/透传 X-Request-ID 作为 trace,响应头回传;完成时记 evt=http。

    SSE 长流:摘要在 response_start(首个 http.response.start)记录,
    ms≈TTFB(D-704);流完整生命周期由 chat.stream done 事件覆盖。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        method = scope.get("method", "?")
        if path.endswith("/health") or method == "OPTIONS":
            await self.app(scope, receive, send)  # 探活零日志
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        incoming = headers.get("x-request-id", "")
        trace = incoming if _VALID_ID.match(incoming) else new_trace()
        token = set_trace(trace)
        t0 = time.monotonic()
        state = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state["code"] = message["status"]
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-request-id", trace.encode()))
                message = dict(message)
                message["headers"] = headers_list
                if not state.get("logged"):
                    state["logged"] = True
                    ms = round((time.monotonic() - t0) * 1000, 1)
                    code = state["code"]
                    if code >= 500:
                        lvl, res = logging.ERROR, "fail"
                    elif code >= 400:
                        lvl, res = logging.WARNING, "ok"  # 业务拒绝非服务故障
                    else:
                        lvl, res = logging.INFO, "ok"
                    log_event(_logger, "http", method.lower(), res,
                              level=lvl, path=path, status=code, ms=ms)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            if not state.get("logged"):
                state["logged"] = True
                ms = round((time.monotonic() - t0) * 1000, 1)
                log_event(_logger, "http", method.lower(), "fail",
                          path=path, status=500, ms=ms, exc=True)
            raise
        finally:
            reset_trace(token)
