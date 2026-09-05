"""
SunChat Backend - Search Route
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict

from services.search_service import search_svc
from services.memory_service import memory_service

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    intent: str = None
    sources: List[str] = None
    use_memory_context: bool = True


class SearchResponse(BaseModel):
    query: str
    intent: str
    results: List[Dict]
    used_memory: List[Dict]


@router.post("/search")
def perform_search(request: SearchRequest):
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

        # 保存搜索历史
        from models.sql_models import get_thread_session, SearchHistory
        db = get_thread_session()
        search_history = SearchHistory(
            user_id=1,
            query=request.query,
            intent=route_result["intent"],
            results_count=len(results)
        )
        db.add(search_history)
        db.commit()
        db.refresh(search_history)

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


@router.get("/search/history")
def list_search_history(page: int = 1, page_size: int = 20):
    """列出搜索历史"""
    from models.sql_models import SearchHistory, get_thread_session
    db = get_thread_session()
    offset = (page - 1) * page_size
    history = db.query(SearchHistory).order_by(
        SearchHistory.created_at.desc()
    ).offset(offset).limit(page_size).all()

    total = db.query(SearchHistory).count()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "history": [
                {
                    "id": h.id,
                    "query": h.query,
                    "intent": h.intent,
                    "results_count": h.results_count,
                    "created_at": h.created_at.isoformat()
                }
                for h in history
            ],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@router.get("/search/suggest")
def search_suggestions(q: str):
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
