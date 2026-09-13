"""
SunChat Backend - Mobile Pair Route (R-014)
局域网配对信息:LAN IP + 移动端 URL,供桌面设置页渲染二维码。
"""
import socket

from fastapi import APIRouter

from app.config import settings
from utils.logger import logger, log_event

router = APIRouter()


def detect_lan_ip() -> str:
    """探测默认出口 IPv4(UDP connect 技巧,不实际发包)。失败返回空串。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return ""
    finally:
        s.close()


@router.get("/pair/info")
def pair_info():
    """R-014: 返回局域网移动端地址(二维码源)。无鉴权(可信内网边界,单用户模式)。"""
    try:
        ip = detect_lan_ip()
        port = settings.PUBLIC_PORT or settings.APP_PORT
        url = f"http://{ip}:{port}/m" if ip else ""
        log_event(logger, "pair", "info", "ok" if ip else "fail",
                  **( {"lan_ip": ip} if ip else {"reason": "no_lan"}))
        return {"code": 200, "message": "success",
                "data": {"lan_ip": ip, "port": port, "url": url}}
    except Exception as e:
        log_event(logger, "pair", "info", "fail", reason="internal",
                  error=str(e)[:120], exc=True)
        return {"code": 200, "message": "success",
                "data": {"lan_ip": "", "port": settings.PUBLIC_PORT or settings.APP_PORT,
                         "url": ""}}
