"""
SunChat Backend - Memories Route
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional

from services.memory_service import memory_service

router = APIRouter()


class MemoryCreateRequest(BaseModel):
    content: str
    type: str = "semantic"
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: int = 5


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[Dict] = None


@router.get("/memories")
def list_memories(
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20)
):
    """列出记忆（简化版）"""
    # 简化实现
    return {
        "code": 200,
        "message": "success",
        "data": {
            "total": 0,
            "memories": []
        }
    }


@router.post("/memories/search")
def search_memories(request: MemorySearchRequest):
    """搜索记忆"""
    try:
        result = memory_service.search_memories(
            user_id=1,
            query=request.query,
            top_k=request.top_k,
            filters=request.filters
        )
        return {
            "code": 200,
            "message": "success",
            "data": {
                "query": request.query,
                "results": result
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories")
def create_memory(request: MemoryCreateRequest):
    """创建记忆"""
    try:
        memory = memory_service.create_memory(
            user_id=1,
            content=request.content,
            memory_type=request.type,
            category=request.category,
            tags=request.tags,
            importance=request.importance
        )
        return {
            "code": 201,
            "message": "记忆创建成功",
            "data": memory
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/memories/{memory_id}")
def update_memory(memory_id: str, request: MemoryCreateRequest):
    """更新记忆"""
    try:
        result = memory_service.update_memory(
            memory_id,
            updates=request
        )
        if not result:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {
            "code": 200,
            "message": "success",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    """删除记忆"""
    try:
        result = memory_service.delete_memory(memory_id)
        if not result:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {
            "code": 200,
            "message": "success",
            "data": {"memory_id": memory_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories/stats")
def get_memory_stats():
    """获取记忆统计"""
    try:
        stats = memory_service.get_stats(user_id=1)
        return {
            "code": 200,
            "message": "success",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
