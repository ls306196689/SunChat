"""
SunChat Backend - Main Application Entry Point
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1.routes import auth, chat, memories, search, knowledge, health


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="SunChat API",
        description="Personal AI Assistant API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由注册
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(memories.router, prefix="/api/v1", tags=["memories"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])

    return app


# 创建应用实例
app = create_app()


@app.get("/")
async def root():
    return {
        "message": "SunChat API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
