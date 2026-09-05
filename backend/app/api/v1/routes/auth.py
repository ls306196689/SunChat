"""
SunChat Backend - Auth Route
诚实的单用户本地模式：无账户体系、无 JWT（多用户为 Roadmap）。

历史 register/login 为返回假 token 的 mock，已移除（假认证比没有认证更危险：
前端若携带 Authorization 头会误以为已鉴权）。保留身份查询端点供前端展示模式。
"""
from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter()

_MULTI_USER_HINT = "本地单用户模式不支持账户操作；多用户/JWT 在 Roadmap（见 README Phase 5+）"


@router.post("/auth/register")
def register():
    """注册：未实现（诚实返回 501，不再返回假 token）"""
    raise HTTPException(status_code=501, detail=_MULTI_USER_HINT)


@router.post("/auth/login")
def login():
    """登录：未实现（诚实返回 501，不再返回假 token）"""
    raise HTTPException(status_code=501, detail=_MULTI_USER_HINT)


@router.get("/auth/me")
def get_me():
    """当前身份（无鉴权，本地模式直接返回单用户标识）"""
    return {
        "code": 200,
        "message": "success",
        "data": {
            "user_id": settings.LOCAL_USER_ID,
            "username": "local_user",
            "mode": "local-single-user"
        }
    }
