"""
SunChat Backend - Knowledge Base Route
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List

from services.knowledge_service import knowledge_service

router = APIRouter()


class KBQuestionRequest(BaseModel):
    file_ids: List[int]
    query: str


@router.post("/kb/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件到知识库"""
    try:
        # 获取文件信息
        filename = file.filename
        file_type = filename.split(".")[-1] if "." in filename else "unknown"
        file_size = 0

        # 读取文件内容计算大小
        content = await file.read()
        file_size = len(content)

        # 保存记录
        result = knowledge_service.upload_file(
            user_id=1,
            filename=filename,
            original_name=filename,
            file_type=file_type,
            file_size=file_size
        )

        return {
            "code": 201,
            "message": "文件上传成功，正在处理",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kb/files")
async def list_files(status: str = None):
    """列出知识库文件"""
    try:
        files = knowledge_service.get_files(user_id=1, status=status)
        return {
            "code": 200,
            "message": "success",
            "data": {"files": files}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/kb/files/{file_id}")
async def delete_file(file_id: int):
    """删除知识库文件"""
    return {
        "code": 200,
        "message": "success",
        "data": {"file_id": file_id}
    }


@router.post("/kb/qa")
async def knowledge_qa(request: KBQuestionRequest):
    """知识库问答"""
    try:
        result = knowledge_service.qa(
            file_ids=request.file_ids,
            query=request.query
        )
        return {
            "code": 200,
            "message": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
