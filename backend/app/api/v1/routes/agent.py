"""
SunChat Backend - Agent Route
Agent 正式端点：原生 tool_calls 循环 + 会话落库。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from core.security import sanitize_input
from core.agent.agent import agent
from services.chat_service import chat_service
from utils.logger import logger, log_event

router = APIRouter()


class AgentRequest(BaseModel):
    content: str
    session_id: Optional[str] = None
    max_iterations: int = 5
    model: Optional[str] = None


@router.post("/chat/agent")
def agent_chat(request: AgentRequest):
    """运行 Agent（可调用记忆/搜索/知识库工具），返回最终答案与工具轨迹。"""
    try:
        ok, reason = sanitize_input(request.content)
        if not ok:
            raise HTTPException(status_code=400, detail=reason)

        user_id = settings.LOCAL_USER_ID
        # R-005: 非空非法 session_id 一律 400(禁止静默丢失历史);空/缺省 = 无会话模式
        session_id = None
        history = None
        if request.session_id:
            if not request.session_id.isdigit():
                raise HTTPException(status_code=400, detail="session_id 非法")
            session_id = int(request.session_id)
            history = chat_service.get_recent_messages(session_id)

        result = agent.run(request.content, user_id=user_id, history=history,
                           model=request.model,
                           max_iterations=max(1, min(request.max_iterations, 10)))

        content = result.get("content", "")
        if not content:
            log_event(logger, "agent", "run", "fail",
                      reason="empty_answer",
                      error=str(result.get("error", "LLM 不可用"))[:120])
            raise HTTPException(
                status_code=503,
                detail=f"Agent 未产生答案: {result.get('error', 'LLM 不可用')}")

        if session_id:
            chat_service.save_user_message(session_id, request.content)
            chat_service.save_assistant_message(session_id, content)

        log_event(logger, "agent", "run", "ok", mode=result.get("mode"),
                  iterations=result.get("iterations"),
                  tools=[t['tool'] for t in result.get('tool_trace', [])])

        return {
            "code": 200,
            "message": "success",
            "data": {
                "result": content,
                "tool_trace": result.get("tool_trace", []),
                "iterations": result.get("iterations", 0),
                "mode": result.get("mode", "text"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        log_event(logger, "agent", "run", "fail", reason="internal",
                  error=str(e)[:120], exc=True)
        raise HTTPException(status_code=500, detail=str(e))
