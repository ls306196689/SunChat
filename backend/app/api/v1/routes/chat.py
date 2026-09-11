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
from pathlib import Path
import json
import re
import uuid
from typing import List, Dict, Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from app.config import settings
from core.security import sanitize_input
from services.chat_service import chat_service
from services.memory_service import memory_service

router = APIRouter()


def _resolve_session_id(raw: str) -> int:
    """R-004: session_id 统一校验（与 PATCH/DELETE 语义对齐）,非法一律 400,禁止静默回退会话1。"""
    if not raw or not raw.isdigit():
        raise HTTPException(status_code=400, detail="session_id 非法")
    return int(raw)


# ==================== R-008: 图片通道 ====================

_IMAGE_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[a-z]{3,4}$")

# 魔数（标准库校验,免新依赖 D-404）→ 规范扩展名 / media_type
_IMAGE_MAGIC = {
    b"\x89PNG\r\n\x1a\n": (".png", "image/png"),
    b"\xff\xd8\xff": (".jpg", "image/jpeg"),
    b"GIF87a": (".gif", "image/gif"),
    b"GIF89a": (".gif", "image/gif"),
}


def _sniff_image(header: bytes):
    """按魔数识别图片真实格式；webp 特判 RIFF....WEBP。命中 → (.ext, media_type)。"""
    for magic, val in _IMAGE_MAGIC.items():
        if header.startswith(magic):
            return val
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return (".webp", "image/webp")
    return None


def _cfg():
    import app.config as _c  # 运行时读取（reload 兼容,同 sql_models 模式）
    return _c.settings


def _image_path(image_id: str) -> Optional[Path]:
    """image_id → 安全路径（uuid 正则+扩展名白名单双校验,D-403/R-005 类穿越防护）。"""
    if not _IMAGE_ID_RE.match(image_id or ""):
        return None
    p = Path(_cfg().CHAT_IMAGE_DIR) / image_id
    if p.suffix not in (".png", ".jpg", ".gif", ".webp"):
        return None
    return p


class ChatRequest(BaseModel):
    session_id: str
    content: str
    memory_context: bool = True
    search_enabled: bool = True
    model: str = None
    stream: bool = False
    images: List[str] = []  # R-008: 附图 image_id 列表


class StreamChatRequest(BaseModel):
    session_id: str
    content: str
    memory_context: bool = True
    search_enabled: bool = True
    model: str = None
    images: List[str] = []  # R-008


def _resolve_images(ids: List[str]) -> List[str]:
    """校验附图 id（非法/缺失 → 400）,返回规范 id 列表。"""
    if not ids:
        return []
    limit = _cfg().CHAT_IMAGE_MAX_PER_MSG
    if len(ids) > limit:
        raise HTTPException(status_code=400, detail=f"单条消息最多 {limit} 张图")
    for iid in ids:
        p = _image_path(iid)
        if p is None:
            raise HTTPException(status_code=400, detail=f"image_id 非法: {iid}")
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"图片不存在: {iid}")
    return list(ids)


@router.post("/chat/images")
async def upload_chat_image(file: UploadFile = File(...)):
    """R-008: 对话图片上传。魔数校验 png/jpg/gif/webp,≤CHAT_IMAGE_MAX_MB,uuid 落盘。"""
    max_mb = _cfg().CHAT_IMAGE_MAX_MB
    data = await file.read(max_mb * 1024 * 1024 + 1)
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"图片超过 {max_mb}MB 限制")
    sniffed = _sniff_image(data[:16])
    if not sniffed:
        raise HTTPException(status_code=400, detail="不支持的图片格式(仅 png/jpg/gif/webp)")
    ext, _mt = sniffed
    image_id = f"{uuid.uuid4()}{ext}"  # 扩展名派生自魔数,不信任客户端 filename（R-005 教训）
    img_dir = Path(_cfg().CHAT_IMAGE_DIR)
    img_dir.mkdir(parents=True, exist_ok=True)
    (img_dir / image_id).write_bytes(data)
    return {"code": 200, "message": "success", "data": {"image_id": image_id}}


@router.get("/chat/images/{image_id}")
def get_chat_image(image_id: str):
    """R-008: 图片回显。id 严格校验防穿越,缺失 404。"""
    p = _image_path(image_id)
    if p is None:
        raise HTTPException(status_code=400, detail="image_id 非法")
    if not p.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    media = {".png": "image/png", ".jpg": "image/jpeg",
             ".gif": "image/gif", ".webp": "image/webp"}[p.suffix]
    return FileResponse(str(p), media_type=media)


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
        ok, reason = sanitize_input(request.content)
        if not ok:
            raise HTTPException(status_code=400, detail=reason)

        # 用户ID固定为本地单用户（诚实模式，见 /whoami）
        user_id = settings.LOCAL_USER_ID

        # 调用chat_service.process_message实现完整流程
        result = chat_service.process_message(
            user_id=user_id,
            session_id=_resolve_session_id(request.session_id),
            content=request.content,
            memory_enabled=request.memory_context,
            search_enabled=request.search_enabled,
            model=request.model,
            images=_resolve_images(request.images)
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
    except HTTPException:
        raise
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
def get_messages(session_id: str,
                 page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=100)):
    """获取消息历史（R-005: session_id 统一400校验,分页限幅 page≥1/1≤page_size≤100）"""
    messages = chat_service.get_messages(
        session_id=_resolve_session_id(session_id),
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


# R-008: 旧 StreamChatRequest 定义已移除,统一用文件头部含 images 字段的定义


def _sse(payload: Dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def stream_chat(request: StreamChatRequest):
    """流式对话（SSE）。

    同步 generator：Starlette 自动放线程池执行，不阻塞事件循环。
    帧协议: {"type":"meta"|"delta"|"done"|"error", ...}
    """
    ok, reason = sanitize_input(request.content)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    user_id = settings.LOCAL_USER_ID
    session_id = _resolve_session_id(request.session_id)
    images = _resolve_images(request.images)  # R-008: 流开始前完成校验(非法→400非SSE错误帧)

    def gen():
        try:
            ctx = chat_service.build_context(
                user_id, session_id, request.content,
                memory_enabled=request.memory_context,
                search_enabled=request.search_enabled,
            )
            # 先行落库用户消息（R-008: 含附图 id）+ 下发记忆/来源元信息
            chat_service.save_user_message(session_id, request.content,
                                           images=request.images)
            yield _sse({"type": "meta",
                        "memory_context": ctx["memory_context"][:3],
                        "sources": ctx["sources"][:5]})

            full = []
            for chunk in chat_service.stream_reply(ctx, request.content,
                                                   model=request.model,
                                                   images=images):
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
