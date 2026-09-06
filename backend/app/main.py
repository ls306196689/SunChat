"""
SunChat Backend - Main Application Entry Point
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, DATA_DIR, UPLOAD_DIR
from app.api.v1.routes import auth, chat, memories, search, knowledge, health, models, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时确保数据目录、建表迁移、模型自检。"""
    from utils.logger import logger

    # 1. 确保数据目录存在（绝对路径，消除 CWD 依赖）
    for d in (DATA_DIR, UPLOAD_DIR, Path(settings.CHROMA_PERSIST_DIR),
              Path(settings.MODEL_CONFIG_PATH).parent):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"[STARTUP] 创建目录失败 {d}: {e}")

    # 2. 建表 + 轻量迁移（旧库补列 / habit 拼写）
    try:
        from models.sql_models import init_db
        init_db()
        logger.info("[STARTUP] 数据库初始化/迁移完成")
    except Exception as e:
        logger.error(f"[STARTUP] 数据库初始化失败: {e}")

    # 3. Ollama 自检（仅记录，不阻断启动）
    try:
        from core.model_manager import model_manager
        ok = model_manager.is_available()
        logger.info(f"[STARTUP] Ollama 可用性: {ok} @ {settings.LLM_API_URL}")
    except Exception as e:
        logger.warning(f"[STARTUP] Ollama 自检失败: {e}")

    # 4. FTS 关键词索引就绪 + 自愈重建
    try:
        from core.fts_index import init_fts, fts_bootstrap_from_sqlite
        if init_fts():
            fts_bootstrap_from_sqlite()
    except Exception as e:
        logger.warning(f"[STARTUP] FTS 初始化失败(关键词通道降级): {e}")

    # 5. 存储一致性对账自愈（SQLite↔Chroma）
    if settings.RECONCILE_ON_STARTUP:
        try:
            from core.model_manager import model_manager
            if model_manager.is_available():
                from services.storage_service import storage_service
                r = storage_service.reconcile()
                p = storage_service.prune_orphan_vectors()
                from core.fts_index import fts_bootstrap_from_sqlite
                fts_bootstrap_from_sqlite()
                logger.info(f"[STARTUP] 记忆对账: {r} 孤儿清理: {p}")
        except Exception as e:
            logger.warning(f"[STARTUP] 记忆对账失败(不阻断): {e}")

    yield

    # 关闭资源（线程 Session 随 worker 线程生命周期，无需显式关闭）


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="SunChat API",
        description="Personal AI Assistant API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS：收敛到本地白名单（本地优先单用户应用）
    allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由注册
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(models.router, prefix="/api/v1", tags=["models"])
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(memories.router, prefix="/api/v1", tags=["memories"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])
    app.include_router(agent.router, prefix="/api/v1", tags=["agent"])

    return app


# 创建应用实例
app = create_app()


@app.get("/")
def root():
    return {
        "message": "SunChat API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/whoami")
def whoami():
    """诚实的单用户本地模式标识（无账户体系，多用户为 Roadmap）。"""
    return {
        "code": 200,
        "message": "success",
        "data": {
            "user_id": settings.LOCAL_USER_ID,
            "username": "local_user",
            "mode": "local-single-user"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
