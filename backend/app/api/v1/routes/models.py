"""
SunChat Backend - Models Route
模型管理：查询可用模型 / 运行时切换 / 向量库重建
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.model_manager import model_manager
from services.memory_service import memory_service
from utils.logger import logger

router = APIRouter()


class SwitchModelRequest(BaseModel):
    model: str


@router.get("/models")
def get_models():
    """获取真实可用模型列表 + 当前模型 + 向量库状态"""
    try:
        status = model_manager.get_status()
        return {
            "code": 200,
            "message": "success",
            "data": status
        }
    except Exception as e:
        logger.error(f"[MODELS] 获取模型状态失败 - 错误:{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/chat")
def switch_chat_model(req: SwitchModelRequest):
    """切换聊天模型（运行时，持久化）"""
    try:
        result = model_manager.set_chat_model(req.model)
        if not result.get("success"):
            return {"code": 400, "message": result.get("error", "切换失败"), "data": result}
        return {"code": 200, "message": "切换成功", "data": result}
    except Exception as e:
        logger.error(f"[MODELS] 切换聊天模型失败 - 错误:{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/embedding")
def switch_embedding_model(req: SwitchModelRequest):
    """切换嵌入模型（运行时，持久化），返回是否需要重建向量库"""
    try:
        result = model_manager.set_embedding_model(req.model)
        if not result.get("success"):
            return {"code": 400, "message": result.get("error", "切换失败"), "data": result}
        return {"code": 200, "message": "切换成功", "data": result}
    except Exception as e:
        logger.error(f"[MODELS] 切换嵌入模型失败 - 错误:{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/rebuild-vectors")
def rebuild_vectors():
    """重建向量库（切换嵌入模型后保证检索准确；支持断点续跑）"""
    try:
        logger.info("[MODELS] 触发向量库重建")
        from services.storage_service import storage_service
        result = storage_service.rebuild()
        if not result.get("success"):
            return {
                "code": 200,
                "message": f"重建完成，但有 {result.get('failed', 0)} 条失败",
                "data": result
            }
        return {"code": 200, "message": "向量库重建成功", "data": result}
    except Exception as e:
        logger.error(f"[MODELS] 向量库重建失败 - 错误:{e}")
        raise HTTPException(status_code=500, detail=str(e))
