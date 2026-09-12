"""
SunChat Backend - Knowledge Base Route
"""
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List

from app.config import settings
from services.knowledge_service import knowledge_service
from utils.logger import logger, log_event

router = APIRouter()

_READ_CHUNK = 1024 * 1024


class KBQuestionRequest(BaseModel):
    file_ids: List[int]
    query: str


def _allowed_types() -> List[str]:
    return [t.strip().lower() for t in settings.ALLOWED_FILE_TYPES.split(",") if t.strip()]


@router.post("/kb/upload")
def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """上传文件到知识库：校验类型/大小 → 落盘 → 记录 → 后台解析入库"""
    try:
        filename = file.filename or "unnamed"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"
        if ext not in _allowed_types():
            log_event(logger, "kb", "upload", "fail", reason="bad_type",
                      ext=ext, filename=filename[:80])
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {ext}（允许: {'/'.join(_allowed_types())}）",
            )

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        size = 0
        # uuid 文件名落盘（防路径穿越/重名），边读边限幅
        storage_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}.{ext}")
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        with open(storage_path, "wb") as out:
            while True:
                chunk = file.file.read(_READ_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    break
                out.write(chunk)
        if size > max_bytes:
            os.remove(storage_path)
            log_event(logger, "kb", "upload", "fail", reason="oversize",
                      size_mb=round(size / 1048576, 1))
            raise HTTPException(status_code=413, detail=f"文件超过大小限制 {settings.MAX_UPLOAD_MB}MB")

        result = knowledge_service.upload_file(
            user_id=settings.LOCAL_USER_ID,
            filename=filename,
            original_name=filename,
            file_type=ext,
            file_size=size,
            storage_path=storage_path,
        )

        # 后台解析入库（process_file 内部已捕获异常并标记 failed）
        background_tasks.add_task(
            knowledge_service.process_file, result["file_id"], storage_path, ext
        )

        log_event(logger, "kb", "upload", "ok", file_id=result["file_id"],
                  size_kb=size // 1024, ext=ext)
        return {
            "code": 201,
            "message": "文件上传成功，正在处理",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        log_event(logger, "kb", "upload", "fail", reason="internal",
                  error=str(e)[:120], exc=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kb/files")
def list_files(status: str = None):
    """列出知识库文件"""
    try:
        files = knowledge_service.get_files(user_id=settings.LOCAL_USER_ID, status=status)
        return {
            "code": 200,
            "message": "success",
            "data": {"files": files}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/kb/files/{file_id}")
def delete_file(file_id: int):
    """删除知识库文件（SQLite 记录 + 分块 + Chroma 向量 + 物理文件）"""
    try:
        ok = knowledge_service.delete_file(file_id)
        if not ok:
            raise HTTPException(status_code=404, detail="文件不存在")
        return {
            "code": 200,
            "message": "success",
            "data": {"file_id": file_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/files/{file_id}/retry")
def retry_file(file_id: int, background_tasks: BackgroundTasks = None):
    """重试处理失败的文件（清理后异步重新解析入库）"""
    try:
        result = knowledge_service.retry_process_file(file_id)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        background_tasks.add_task(
            knowledge_service.process_file,
            file_id, result["storage_path"], result["file_type"],
        )
        return {"code": 200, "message": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/qa")
def knowledge_qa(request: KBQuestionRequest):
    """知识库问答"""
    try:
        result = knowledge_service.qa(
            file_ids=request.file_ids,
            query=request.query,
            user_id=settings.LOCAL_USER_ID,
        )
        return {
            "code": 200,
            "message": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
