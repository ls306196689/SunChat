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
from typing import List, Dict, Optional, AsyncGenerator
import uuid
import json
import asyncio

from app.config import settings
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
        # 用户ID固定为本地单用户（诚实模式，见 /whoami）
        user_id = settings.LOCAL_USER_ID

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
                "sources": result.get("sources", []),
                "tokens_used": result.get("tokens_used", 0)
            }
        }

    except RuntimeError as e:
        # LLM 不可用/空响应：明确 503，且不落空 assistant 消息
        raise HTTPException(status_code=503, detail=f"LLM 服务暂不可用: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions")
def list_sessions():
    """获取会话列表（当前用户、排除软删除）"""
    from models.sql_models import ChatSession, get_thread_session
    db = get_thread_session()
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == settings.LOCAL_USER_ID,
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
    session = chat_service.create_session(user_id=settings.LOCAL_USER_ID)
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
    """更新会话标题（真实落库）"""
    try:
        ok = chat_service.rename_session(int(session_id), title)
        if not ok:
            raise HTTPException(status_code=404, detail="会话不存在")
        return {
            "code": 200,
            "message": "success",
            "data": {"session_id": session_id, "title": title}
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="session_id 非法")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str):
    """删除会话（软删除）"""
    try:
        ok = chat_service.delete_session(int(session_id))
        if not ok:
            raise HTTPException(status_code=404, detail="会话不存在")
        return {
            "code": 200,
            "message": "success",
            "data": {"session_id": session_id}
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="session_id 非法")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class StreamChatRequest(BaseModel):
    session_id: str
    content: str
    memory_context: bool = True
    search_enabled: bool = True
    model: str = None


def _sse(payload: Dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def stream_chat(request: StreamChatRequest):
    """流式对话（SSE）。

    同步 generator：Starlette 自动放线程池执行，不阻塞事件循环。
    帧协议: {"type":"meta"|"delta"|"done"|"error", ...}
    """
    user_id = settings.LOCAL_USER_ID
    try:
        session_id = int(request.session_id) if request.session_id.isdigit() else 1
    except ValueError:
        raise HTTPException(status_code=400, detail="session_id 非法")

    def gen():
        try:
            ctx = chat_service.build_context(
                user_id, session_id, request.content,
                memory_enabled=request.memory_context,
                search_enabled=request.search_enabled,
            )
            # 先行落库用户消息 + 下发记忆/来源元信息
            chat_service.save_user_message(session_id, request.content)
            yield _sse({"type": "meta",
                        "memory_context": ctx["memory_context"][:3],
                        "sources": ctx["sources"][:5]})

            full = []
            for chunk in chat_service.stream_reply(ctx, request.content,
                                                   model=request.model):
                if not chunk:
                    continue
                full.append(chunk)
                yield _sse({"type": "delta", "content": chunk})

            text = "".join(full)
            if not text:
                raise RuntimeError("LLM 返回空内容")
            chat_service.finalize_stream(
                user_id, session_id, request.content, text, ctx,
                memory_enabled=request.memory_context)
            yield _sse({"type": "done", "content": "", "done": True})
        except Exception as e:
            yield _sse({"type": "error", "error": str(e), "done": True})

    return StreamingResponse(gen(), media_type="text/event-stream")
