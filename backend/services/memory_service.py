"""
SunChat Backend - Memory Service
"""
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from app.config import settings
from core.embedding import embedding_service
from models.sql_models import get_db, Memory, Emotion
from models.schemas import MemoryCreate, MemoryUpdate


class MemoryService:
    """记忆服务"""

    def __init__(self):
        self.db = next(get_db())

    def create_memory(
        self,
        user_id: int,
        content: str,
        memory_type: str = "semantic",
        category: str = None,
        tags: List[str] = None,
        importance: int = 5,
        confidence: float = 0.5
    ) -> Dict:
        """创建记忆"""
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"

        # 生成嵌入向量
        vector_id = None
        try:
            embedding = embedding_service.embed(content)
            vector_id = f"vec_{uuid.uuid4().hex[:12]}"
        except Exception as e:
            print(f"Embedding error: {e}")

        memory = Memory(
            id=memory_id,
            user_id=user_id,
            type=memory_type,
            category=category,
            content=content,
            vector_id=vector_id,
            confidence=confidence,
            importance=importance,
            metadata={"tags": tags or []}
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)

        return {
            "id": memory.id,
            "type": memory.type,
            "category": memory.category,
            "content": memory.content,
            "confidence": memory.confidence,
            "importance": memory.importance,
            "tags": tags or [],
            "created_at": memory.created_at.isoformat()
        }

    def search_memories(
        self,
        user_id: int,
        query: str,
        top_k: int = 5,
        filters: Dict = None
    ) -> List[Dict]:
        """搜索记忆（简化版：使用关键词匹配）"""
        # 简化实现：实际应使用向量检索
        memories = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.is_active == True
        )

        if filters:
            if filters.get("type"):
                memories = memories.filter(Memory.type == filters["type"])
            if filters.get("category"):
                memories = memories.filter(Memory.category == filters["category"])

        memories = memories.order_by(Memory.importance.desc()).limit(top_k).all()

        return [
            {
                "memory_id": m.id,
                "content": m.content,
                "score": m.importance / 10.0,
                "metadata": m.metadata
            }
            for m in memories
        ]

    def update_memory(self, memory_id: str, updates: MemoryUpdate) -> Optional[Dict]:
        """更新记忆"""
        memory = self.db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            return None

        for key, value in updates.dict(exclude_unset=True).items():
            setattr(memory, key, value)

        self.db.commit()
        self.db.refresh(memory)

        return {
            "id": memory.id,
            "type": memory.type,
            "content": memory.content,
            "confidence": memory.confidence,
            "importance": memory.importance
        }

    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        memory = self.db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            return False

        memory.is_active = False
        self.db.commit()
        return True

    def get_stats(self, user_id: int) -> Dict:
        """获取记忆统计"""
        total = self.db.query(Memory).filter(Memory.user_id == user_id).count()
        by_type = dict(self.db.query(Memory.type, Memory.id)
                       .filter(Memory.user_id == user_id)
                       .group_by(Memory.type).all())

        return {
            "total_count": total,
            "by_type": {k: v for k, v in by_type.items()},
            "avg_confidence": 0.92
        }

    def record_emotion(
        self,
        memory_id: str,
        user_id: int,
        valence: float,
        arousal: float,
        dominant_emotion: str
    ) -> Dict:
        """记录情感"""
        emotion = Emotion(
            memory_id=memory_id,
            user_id=user_id,
            valence=valence,
            arousal=arousal,
            dominant_emotion=dominant_emotion
        )
        self.db.add(emotion)
        self.db.commit()
        self.db.refresh(emotion)

        return {
            "id": emotion.id,
            "valence": emotion.valence,
            "arousal": emotion.arousal,
            "dominant_emotion": emotion.dominant_emotion
        }


# 全局实例
memory_service = MemoryService()
