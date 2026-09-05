"""
SunChat Backend - Chat Route
实现对话流程：
1. 用户输入信息
2. 构建prompt + 用户输入信息 给llm, 看需要查询什么记忆
3. 按照llm提示查询本地记忆
4. 本地记忆查询内容 + 用户输入信息 + 记忆提取prompt 给到llm
5. llm 返回记忆提取内容 以及 对用户输入信息的回复
6. 本地服务更新记忆,如果有冲突以最新记忆为准
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, AsyncGenerator
import uuid
import json
import asyncio

from services.chat_service import chat_service
from services.memory_service import memory_service

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    content: str
    memory_context: bool = True
    search_enabled: bool = True
    model: str = None
    stream: bool = False


class StreamResponse(BaseModel):
    type: str
    content: str
    done: bool = False
    error: str = None


@router.post("/chat/messages")
def create_message(request: ChatRequest):
    """
    发送消息 - 实现完整的对话流程

    流程：
    1. 用户输入信息
    2. 构建prompt + 用户输入信息 给llm, 看需要查询什么记忆
    3. 按照llm提示查询本地记忆
    4. 本地记忆查询内容 + 用户输入信息 + 记忆提取prompt 给到llm
    5. llm 返回记忆提取内容 以及 对用户输入信息的回复
    6. 本地服务更新记忆,如果有冲突以最新记忆为准
    """
    try:
        # 用户ID固定为1（实际应该从认证中获取）
        user_id = 1

        # 调用chat_service.process_message实现完整流程
        result = chat_service.process_message(
            user_id=user_id,
            session_id=int(request.session_id) if request.session_id.isdigit() else 1,
            content=request.content,
            memory_enabled=request.memory_context,
            search_enabled=request.search_enabled,
            model=request.model
        )

        return {
            "code": 200,
            "message": "success",
            "data": {
                "response": result.get("response", ""),
                "memory_updates": result.get("memory_updates", []),
                "memory_context": result.get("memory_context", []),
                "analysis_result": result.get("analysis_result", {}),
                "tokens_used": result.get("tokens_used", 0)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions")
def list_sessions():
    """获取会话列表"""
    from models.sql_models import ChatSession, get_thread_session
    db = get_thread_session()
    sessions = db.query(ChatSession).filter(
        ChatSession.deleted_at == None
    ).order_by(ChatSession.updated_at.desc()).limit(50).all()
    return {
        "code": 200,
        "message": "success",
        "data": [
            {
                "session_id": str(s.id),
                "title": s.title,
                "created_at": s.created_at.isoformat()
            }
            for s in sessions
        ]
    }


@router.post("/chat/sessions")
def create_session():
    """创建会话"""
    session = chat_service.create_session(user_id=1)
    return {
        "code": 201,
        "message": "会话创建成功",
        "data": session
    }


@router.get("/chat/sessions/{session_id}/messages")
def get_messages(session_id: str, page: int = 1, page_size: int = 20):
    """获取消息历史"""
    messages = chat_service.get_messages(
        session_id=int(session_id),
        page=page,
        page_size=page_size
    )
    return {
        "code": 200,
        "message": "success",
        "data": messages
    }


@router.patch("/chat/sessions/{session_id}")
def update_session(session_id: str, title: str):
    """更新会话标题"""
    return {
        "code": 200,
        "message": "success",
        "data": {"session_id": session_id, "title": title}
    }


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str):
    """删除会话"""
    return {
        "code": 200,
        "message": "success",
        "data": {"session_id": session_id}
    }
