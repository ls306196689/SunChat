"""
SunChat Backend - Chat Route
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, AsyncGenerator
import uuid

from services.chat_service import chat_service
from services.memory_service import memory_service

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    content: str
    memory_context: bool = True
    search_enabled: bool = True
    model: str = None


class ChatResponse(BaseModel):
    response: str
    memory_updates: List[Dict]
    tokens_used: int


@router.post("/chat/messages")
async def create_message(request: ChatRequest) -> ChatResponse:
    """发送消息"""
    try:
        # 获取记忆上下文
        memories = []
        if request.memory_context:
            memories = chat_service.build_memory_context(
                user_id=1,  # 本地模式固定为1
                query=request.content
            )

        # 构建 prompt
        system_prompt = "你是一个智能助手。请回答用户问题。"
        if memories:
            system_prompt += f"\n\n用户背景信息：\n" + "\n".join([m["content"] for m in memories])

        full_prompt = f"{system_prompt}\n\n用户: {request.content}\n\nAI:"

        # 调用 LLM
        response = chat_service.generate(full_prompt)

        # 提取记忆
        new_memories = chat_service.generate_memory_from_message(
            request.content, response
        )

        # 保存记忆
        for mem in new_memories:
            memory_service.create_memory(
                user_id=1,
                content=mem["content"],
                memory_type=mem["type"],
                category=mem.get("category"),
                importance=mem.get("importance", 5)
            )

        return ChatResponse(
            response=response,
            memory_updates=new_memories,
            tokens_used=len(response) // 4
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions")
async def list_sessions():
    """获取会话列表"""
    from models.sql_models import ChatSession, get_db
    db = next(get_db())
    sessions = db.query(ChatSession).filter(
        ChatSession.deleted_at == None
    ).order_by(ChatSession.updated_at.desc()).limit(50).all()
    db.close()
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
async def create_session():
    """创建会话"""
    session = chat_service.create_session(user_id=1)
    return {
        "code": 201,
        "message": "会话创建成功",
        "data": session
    }


@router.get("/chat/sessions/{session_id}/messages")
async def get_messages(session_id: str, page: int = 1, page_size: int = 20):
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
async def update_session(session_id: str, title: str):
    """更新会话标题"""
    return {
        "code": 200,
        "message": "success",
        "data": {"session_id": session_id, "title": title}
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    return {
        "code": 200,
        "message": "success",
        "data": {"session_id": session_id}
    }
