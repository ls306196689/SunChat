"""
SunChat Backend - Health Check Route
"""
from fastapi import APIRouter, Depends
from app.config import settings
from core.llm import ollama_service
from core.model_manager import model_manager
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
            "llm_model": model_manager.resolve_chat_model(),
            "embedding_model": model_manager.resolve_embedding_model(),
            "version": "1.0.0"
        }
    }


# 模型列表与切换接口已迁移到 models.py（GET /api/v1/models 等）
