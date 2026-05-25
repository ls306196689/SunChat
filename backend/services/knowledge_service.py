"""
SunChat Backend - Knowledge Base Service
"""
from typing import List, Dict
from models.sql_models import get_db, KBFile, KBChunk


class KnowledgeService:
    """知识库服务"""

    def __init__(self):
        self.db = next(get_db())

    def upload_file(self, user_id: int, filename: str, original_name: str,
                    file_type: str, file_size: int) -> Dict:
        """上传文件（仅记录元数据）"""
        kb_file = KBFile(
            user_id=user_id,
            filename=filename,
            original_name=original_name,
            file_type=file_type,
            file_size=file_size,
            status="uploading"
        )
        self.db.add(kb_file)
        self.db.commit()
        self.db.refresh(kb_file)

        return {
            "file_id": kb_file.id,
            "filename": kb_file.filename,
            "status": kb_file.status
        }

    def process_file(self, file_id: int, chunks: List[Dict]) -> Dict:
        """处理文件（分块并生成向量）"""
        kb_file = self.db.query(KBFile).filter(KBFile.id == file_id).first()
        if not kb_file:
            return {"error": "File not found"}

        # 保存分块
        vector_ids = []
        for i, chunk in enumerate(chunks):
            kb_chunk = KBChunk(
                file_id=file_id,
                chunk_index=i,
                content=chunk["content"],
                vector_id=chunk.get("vector_id", ""),
                token_count=chunk.get("token_count", 0)
            )
            self.db.add(kb_chunk)
            vector_ids.append(chunk.get("vector_id", ""))

        kb_file.status = "ready"
        kb_file.chunk_count = len(chunks)
        kb_file.vector_ids = vector_ids
        self.db.commit()

        return {
            "file_id": file_id,
            "status": "ready",
            "chunk_count": len(chunks)
        }

    def get_files(self, user_id: int, status: str = None) -> List[Dict]:
        """获取文件列表"""
        query = self.db.query(KBFile).filter(KBFile.user_id == user_id)

        if status:
            query = query.filter(KBFile.status == status)

        files = query.order_by(KBFile.created_at.desc()).all()

        return [
            {
                "id": f.id,
                "filename": f.filename,
                "original_name": f.original_name,
                "file_type": f.file_type,
                "file_size": f.file_size,
                "status": f.status,
                "chunk_count": f.chunk_count,
                "created_at": f.created_at.isoformat()
            }
            for f in files
        ]

    def qa(self, file_ids: List[int], query: str) -> Dict:
        """知识库问答"""
        # 简化实现：返回模拟结果
        return {
            "answer": f"根据文档内容，关于'{query}'的信息如下：这是模拟回答，实际应通过向量检索获取。",
            "sources": [
                {
                    "file_id": file_ids[0],
                    "relevance": 0.92
                }
            ]
        }


# 全局实例
knowledge_service = KnowledgeService()
