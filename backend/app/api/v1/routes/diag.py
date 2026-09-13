"""
SunChat Backend - Client Diagnostics Route (R-016)
手机端交互日志汇入:移动浏览器 drop_console 无现场 → 阶段事件批量回传落 evt=mobile.diag。
边界=可信内网(与 pair 一致,单用户模式,无鉴权);批量上限+截断防刷(R-016/R-1)。
"""
import json

from fastapi import APIRouter, HTTPException

from utils.logger import logger, log_event

router = APIRouter()

_MAX_EVENTS = 50
_MAX_MSG = 500
_MAX_PAGE = 64
_MAX_STEP = 40
_MAX_EXTRA = 1024


def _clean(s, limit: int) -> str:
    s = str(s)[:limit]
    return s.replace("|", "/").replace("\n", " ").replace("\r", " ")


@router.post("/diag/client")
def diag_client(payload: dict):
    """接收 {page, events:[{ts,lvl,step,msg,extra?}]} → 每事件一行 evt=mobile.diag。

    接收面自身可诊断:任何解析异常单行 fail(400),诊断通道不作故障源。
    """
    try:
        if not isinstance(payload, dict):
            raise ValueError("payload not object")
        page = _clean(payload.get("page", "?"), _MAX_PAGE)
        events = payload.get("events")
        if not isinstance(events, list) or not events:
            raise ValueError("events empty/invalid")
        n = 0
        for ev in events[:_MAX_EVENTS]:
            if not isinstance(ev, dict):
                continue
            step = _clean(ev.get("step", "?"), _MAX_STEP)
            lvl = ev.get("lvl") if ev.get("lvl") in ("info", "warn", "err") else "info"
            msg = _clean(ev.get("msg", ""), _MAX_MSG)
            ts = ev.get("ts")
            extra = ev.get("extra")
            if isinstance(extra, (dict, list)):
                extra = json.dumps(extra, ensure_ascii=False, default=str)
            extra = _clean(extra, _MAX_EXTRA) if extra is not None else ""
            fields = {"page": page, "step": step, "lvl": lvl, "msg": msg}
            if isinstance(ts, (int, float)) and not isinstance(ts, bool):
                fields["ts"] = int(ts)
            if extra:
                fields["extra"] = extra
            log_event(logger, "mobile", "diag", "ok",
                      level=40 if lvl == "err" else None, **fields)
            n += 1
        if len(events) > _MAX_EVENTS:
            log_event(logger, "diag", "ingest", "skip", reason="overflow",
                      dropped=len(events) - _MAX_EVENTS, page=page)
        return {"code": 200, "message": "success", "data": {"ok": True, "n": n}}
    except Exception as e:
        log_event(logger, "diag", "ingest", "fail", reason="bad_payload",
                  error=str(e)[:120])
        raise HTTPException(status_code=400,
                            detail=f"invalid diag payload: {str(e)[:120]}")
