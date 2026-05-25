"""
SunChat Backend - Health Check Route
"""
from fastapi import APIRouter, Depends
from app.config import settings
from core.llm import ollama_service
from core.search import search_service

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查"""
    llm_available = ollama_service.check_availability()
    search_available = search_service.check_availability()

    return {
        "code": 200,
        "message": "healthy",
        "data": {
            "status": "healthy",
            "llm_available": llm_available,
            "search_available": search_available,
            "llm_model": settings.LLM_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "version": "1.0.0"
        }
    }


@router.get("/models")
async def get_models():
    """获取可用模型列表"""
    return {
        "code": 200,
        "message": "success",
        "data": {
            "llm_models": [
                {"name": settings.LLM_MODEL, "available": True}
            ],
            "embedding_models": [
                {"name": settings.EMBEDDING_MODEL, "available": True}
            ]
        }
    }
