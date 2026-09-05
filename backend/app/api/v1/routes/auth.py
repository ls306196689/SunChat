"""
SunChat Backend - Auth Route
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
security = HTTPBearer()


# 简化实现：本地模式不需要真实认证
@router.post("/register")
def register(request: BaseModel):
    """用户注册（本地模式简化）"""
    return {
        "code": 201,
        "message": "注册成功",
        "data": {"user_id": "user_local", "username": "local_user"}
    }


@router.post("/login")
def login(request: BaseModel):
    """用户登录（本地模式简化）"""
    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "user_id": "user_local",
            "username": "local_user",
            "token": "mock_token"
        }
    }


@router.get("/me")
def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    return {
        "code": 200,
        "message": "success",
        "data": {
            "user_id": "user_local",
            "username": "local_user"
        }
    }
