"""
SunChat Backend - Search Route
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict

from services.search_service import search_svc

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    intent: str = None
    sources: List[str] = None
    use_memory_context: bool = True


@router.post("/search")
async def perform_search(request: SearchRequest):
    """执行搜索"""
    try:
        # 检索记忆
        memories = []
        if request.use_memory_context:
            memories = memory_service.search_memories(
                user_id=1,
                query=request.query,
                top_k=3
            )

        # 智能路由
        route_result = search_svc.route_query(request.query, memories)

        # 执行搜索
        results = search_svc.search(
            query=route_result["query"],
            intent=route_result["intent"]
        )

        return {
            "code": 200,
            "message": "success",
            "data": {
                "query": request.query,
                "intent": route_result["intent"],
                "results": results,
                "used_memory": memories
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/suggest")
async def search_suggestions(q: str):
    """搜索建议"""
    return {
        "code": 200,
        "message": "success",
        "data": {
            "query": q,
            "suggestions": [
                f"{q} 最新",
                f"{q} 教程",
                f"{q} 入门"
            ]
        }
    }


# 导入 memory_service
from services.memory_service import memory_service
