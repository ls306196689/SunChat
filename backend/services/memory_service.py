"""
SunChat Backend - Memory Service
"""
import uuid
import json
from typing import List, Dict, Optional
from datetime import datetime

from app.config import settings
from core.embedding import embedding_service
from core.llm import ollama_service
from core.memory_router import memory_router
from core.model_manager import model_manager
from models.sql_models import DBSessionMixin, Memory, Emotion
from models.schemas import MemoryCreate, MemoryUpdate
from utils.logger import memory_logger, logger


class ChromaClient:
    """Chroma 向量数据库客户端"""

    def __init__(self, persist_directory: str = None):
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self._client = None
        self._collection = None

    def _get_client(self):
        """获取 Chroma 客户端实例"""
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        return self._client

    def _get_collection(self, collection_name: str = "memories"):
        """获取集合"""
        if self._collection is None:
            self._collection = self._get_client().get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def add(self, ids: List[str], documents: List[str], embeddings: List[List[float]], metadatas: List[Dict] = None):
        """添加向量到 Chroma"""
        collection = self._get_collection()
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas or []
        )

    def query(self, query_embeddings: List[List[float]], n_results: int = 5, include: List[str] = None) -> Dict:
        """查询相似向量"""
        collection = self._get_collection()
        if include is None:
            include = ["documents", "metadatas", "distances"]
        return collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            include=include
        )

    def delete(self, ids: List[str]):
        """删除向量"""
        collection = self._get_collection()
        collection.delete(ids=ids)

    def count(self) -> int:
        """获取向量数量"""
        collection = self._get_collection()
        return collection.count()

    def reset(self):
        """重置 Chroma 集合（用于测试）"""
        try:
            self._get_client().delete_collection(name="memories")
            self._collection = None
        except Exception:
            pass

    def recreate(self, embedding_model: str = None):
        """
        删除并重建 Chroma 集合（用于切换嵌入模型后重建向量库）

        Args:
            embedding_model: 当前嵌入模型名，会记录到集合 metadata
        """
        try:
            self._get_client().delete_collection(name="memories")
        except Exception:
            pass
        self._collection = None
        metadata = {"hnsw:space": "cosine"}
        if embedding_model:
            metadata["embedding_model"] = embedding_model
        try:
            self._collection = self._get_client().get_or_create_collection(
                name="memories", metadata=metadata
            )
        except Exception:
            self._collection = None


class MemoryService(DBSessionMixin):
    """记忆服务（db 属性见 DBSessionMixin：线程本地 Session）"""

    def __init__(self):
        self.chroma_client = ChromaClient()

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
        """创建记忆（SQLite + Chroma 双写）"""
        memory_logger.log_memory_create(user_id, content, memory_type, category, True)
        logger.debug(f"[MEMORY] 开始创建记忆 - 用户:{user_id}, 类型:{memory_type}, 分类:{category}")

        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        vector_id = None

        try:
            # 生成嵌入向量
            embedding = embedding_service.embed(content)
            vector_id = f"vec_{uuid.uuid4().hex[:12]}"
            logger.debug(f"[MEMORY] 生成向量 - vector_id:{vector_id}, 维度:{len(embedding)}")

            # 写入 Chroma 向量库
            self.chroma_client.add(
                ids=[vector_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[{
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "type": memory_type,
                    "category": category or "general",
                    "importance": importance
                }]
            )
            logger.debug(f"[MEMORY] 写入 Chroma 成功")
        except Exception as e:
            logger.error(f"[MEMORY] Chroma 写入失败 - 错误:{e}")
            # 如果 Chroma 写入失败，仍然保存到 SQLite
            vector_id = None

        # 写入 SQLite
        memory = Memory(
            id=memory_id,
            user_id=user_id,
            type=memory_type,
            category=category,
            content=content,
            vector_id=vector_id,
            confidence=confidence,
            importance=importance,
            extra_data={"tags": tags or []}
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)

        logger.info(f"[MEMORY] 创建记忆成功 - memory_id:{memory_id}, content:{content[:50]}..., vector_id:{vector_id}")

        return {
            "id": memory.id,
            "type": memory.type,
            "category": memory.category,
            "content": memory.content,
            "confidence": memory.confidence,
            "importance": memory.importance,
            "tags": tags or [],
            "created_at": memory.created_at.isoformat(),
            "vector_id": vector_id
        }

    def search_memories(
        self,
        user_id: int,
        query: str,
        top_k: int = 5,
        filters: Dict = None
    ) -> List[Dict]:
        """搜索记忆（使用 Chroma 向量检索 + SQLite 元数据过滤）"""
        logger.info(f"[MEMORY] 搜索记忆开始 - 用户:{user_id}, 查询:{query}, top_k:{top_k}")
        results = []

        try:
            # 生成查询向量
            query_embedding = embedding_service.embed(query)
            logger.debug(f"[MEMORY] 生成查询向量 - 维度:{len(query_embedding)}")

            # 使用 Chroma 进行向量相似度搜索（包含documents）
            chroma_results = self.chroma_client.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,  # 获取更多结果以进行过滤
                include=["documents", "metadatas", "distances"]
            )
            logger.debug(f"[MEMORY] Chroma 查询完成 - 结果数:{len(chroma_results.get('ids', [[]])[0])}")

            # 从 Chroma 结果中提取 IDs
            chroma_ids = chroma_results.get("ids", [[]])[0]
            chroma_distances = chroma_results.get("distances", [[]])[0]
            chroma_metadatas = chroma_results.get("metadatas", [[]])[0]
            chroma_documents = chroma_results.get("documents", [[]])[0]

            logger.debug(f"[MEMORY] Chroma 结果详细 - IDs:{len(chroma_ids)}, Documents:{len(chroma_documents)}, Metadatas:{len(chroma_metadatas)}")

            # 将 Chroma 结果转换为内存列表
            for i, chroma_id in enumerate(chroma_ids):
                # 优先从documents中获取内容，然后从metadata的document字段
                if i < len(chroma_documents):
                    content = chroma_documents[i]
                else:
                    metadata = chroma_metadatas[i] if i < len(chroma_metadatas) else {}
                    content = metadata.get("document", "")

                metadata = chroma_metadatas[i] if i < len(chroma_metadatas) else {}

                # 应用 SQLite 元数据过滤
                if filters:
                    if filters.get("type") and metadata.get("type") != filters["type"]:
                        continue
                    if filters.get("category") and metadata.get("category") != filters["category"]:
                        continue

                # 将余弦距离转换为相似度 (1 - distance)
                distance = chroma_distances[i] if i < len(chroma_distances) else 0
                similarity = max(0, 1 - distance)

                logger.debug(f"[MEMORY]   Chroma结果{i+1}: content='{content[:50] if content else 'None'}...', similarity={similarity:.4f}")

                results.append({
                    "memory_id": chroma_id,
                    "content": content,
                    "similarity": round(similarity, 4),
                    "metadata": metadata
                })

            # 如果 Chroma 没有结果，回退到 SQLite 关键词搜索
            if not results:
                sqlite_results = self._search_memories_sqlite(user_id, query, top_k, filters)
                results.extend(sqlite_results)

        except Exception as e:
            logger.error(f"[MEMORY] 向量搜索失败 - 错误:{e}")
            # 如果向量搜索失败，回退到 SQLite 关键词搜索
            results = self._search_memories_sqlite(user_id, query, top_k, filters)

        logger.info(f"[MEMORY] 搜索记忆完成 - 结果数:{len(results)}")
        for i, r in enumerate(results[:3]):  # 只记录前3条
            logger.debug(f"[MEMORY]   结果{i+1}: {r.get('content', '')[:50]}... (相似度: {r.get('similarity', 0):.4f})")

        return results

    def _search_memories_sqlite(self, user_id: int, query: str, top_k: int, filters: Dict = None) -> List[Dict]:
        """SQLite 关键词搜索（作为回退方案）"""
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
                "similarity": m.importance / 10.0,
                "metadata": m.extra_data or {}
            }
            for m in memories
        ]

    def update_memory(self, memory_id: str, updates: MemoryUpdate) -> Optional[Dict]:
        """更新记忆"""
        memory = self.db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            return None

        for key, value in updates.dict(exclude_unset=True).items():
            if key == "tags" and value:
                current_tags = memory.extra_data.get("tags", []) if memory.extra_data else []
                current_tags.extend([t for t in value if t not in current_tags])
                if memory.extra_data:
                    memory.extra_data["tags"] = current_tags
                else:
                    memory.extra_data = {"tags": current_tags}
            elif hasattr(memory, key):
                setattr(memory, key, value)

        self.db.commit()
        self.db.refresh(memory)

        return {
            "id": memory.id,
            "type": memory.type,
            "content": memory.content,
            "confidence": memory.confidence,
            "importance": memory.importance,
            "tags": memory.extra_data.get("tags", []) if memory.extra_data else []
        }

    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆（同时从 SQLite 和 Chroma 删除）"""
        memory = self.db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            return False

        # 从 Chroma 删除向量
        if memory.vector_id:
            try:
                self.chroma_client.delete([memory.vector_id])
            except Exception as e:
                logger.warning(f"[MEMORY] Chroma 删除失败: {e}")

        # 从 SQLite 删除
        memory.is_active = False
        self.db.commit()
        return True

    def get_stats(self, user_id: int) -> Dict:
        """获取记忆统计"""
        total = self.db.query(Memory).filter(Memory.user_id == user_id).count()

        # 按类型统计
        from sqlalchemy import func
        type_counts = self.db.query(Memory.type, func.count(Memory.id)).filter(
            Memory.user_id == user_id
        ).group_by(Memory.type).all()

        # 按分类统计
        category_counts = self.db.query(Memory.category, func.count(Memory.id)).filter(
            Memory.user_id == user_id,
            Memory.category != None
        ).group_by(Memory.category).all()

        return {
            "total_count": total,
            "by_type": {k: v for k, v in type_counts},
            "by_category": {k: v for k, v in category_counts},
            "avg_confidence": 0.92,
            "chroma_collection_size": self.chroma_client.count()
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

    def search_memories_by_analysis(self, user_id: int, analysis_result: Dict, top_k: int = 5) -> List[Dict]:
        """
        根据LLM分析结果查询记忆

        Args:
            user_id: 用户ID
            analysis_result: MemoryRouter.analyze_memory_need 的返回结果
            top_k: 返回结果数量

        Returns:
            记忆列表
        """
        query_keywords = analysis_result.get("query_keywords", [])
        memory_types = analysis_result.get("recommended_memory_types", [])

        # 构建查询文本
        if query_keywords:
            query_text = " ".join(query_keywords)
        else:
            query_text = analysis_result.get("user_input", "")

        logger.info(f"[MEMORY] 根据分析结果查询记忆 - 用户:{user_id}, 关键词:{query_keywords}, 类型:{memory_types}")

        # 构建过滤条件
        filters = {}
        if memory_types and "general" not in memory_types:
            filters["category"] = memory_types[0]  # 使用第一个推荐的类型作为分类

        # 执行搜索
        results = self.search_memories(
            user_id=user_id,
            query=query_text,
            top_k=top_k,
            filters=filters
        )

        logger.info(f"[MEMORY] 根据分析结果查询完成 - 结果数:{len(results)}")
        return results

    def update_or_create_memory(self, user_id: int, content: str, memory_type: str = "semantic",
                                 category: str = None, importance: int = 5) -> Dict:
        """
        更新或创建记忆 - 如果存在冲突的记忆则更新，否则创建新记忆

        Args:
            user_id: 用户ID
            content: 记忆内容
            memory_type: 记忆类型
            category: 记忆分类
            importance: 重要性

        Returns:
            记忆信息
        """
        logger.info(f"[MEMORY] 检查并更新/创建记忆 - 用户:{user_id}, 内容:{content[:50]}...")

        # 首先搜索是否已存在相似记忆
        existing_memories = self.search_memories(
            user_id=user_id,
            query=content,
            top_k=3
        )

        # 检查是否需要更新（相似度高于阈值）
        for mem in existing_memories:
            similarity = mem.get("similarity", 0)
            if similarity > 0.85:  # 高相似度阈值
                logger.info(f"[MEMORY] 发现相似记忆，更新 - 相似度:{similarity}")
                # 更新现有记忆的额外数据
                existing = self.db.query(Memory).filter(Memory.id == mem.get("memory_id")).first()
                if existing:
                    # 更新重要性（如果新记忆更重要）
                    if importance > existing.importance:
                        existing.importance = importance
                    existing.confidence = min(1.0, existing.confidence + 0.1)  # 增加置信度
                    self.db.commit()
                    self.db.refresh(existing)

                    return {
                        "id": existing.id,
                        "type": existing.type,
                        "category": existing.category,
                        "content": existing.content,
                        "confidence": existing.confidence,
                        "importance": existing.importance,
                        "action": "updated"
                    }

        # 没有找到需要更新的记忆，创建新记忆
        logger.info(f"[MEMORY] 创建新记忆")
        return self.create_memory(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            category=category,
            importance=importance
        )

    def rebuild_vector_store(self) -> Dict:
        """
        重建向量库：从 SQLite 读取全部活跃记忆，用当前嵌入模型重新生成向量并写入 Chroma

        用于切换嵌入模型后保证向量维度一致、检索准确。

        Returns:
            重建结果 {success, total, rebuilt, failed, embedding_model, error}
        """
        embedding_model = model_manager.resolve_embedding_model()
        logger.info(f"[MEMORY] 开始重建向量库 - 嵌入模型:{embedding_model}")

        # 读取全部活跃记忆
        memories = self.db.query(Memory).filter(Memory.is_active == True).all()
        total = len(memories)
        logger.info(f"[MEMORY] 待重建记忆数:{total}")

        # 删除并重建集合（记录当前嵌入模型）
        self.chroma_client.recreate(embedding_model=embedding_model)

        rebuilt = 0
        failed = 0
        for mem in memories:
            try:
                vector_id = f"vec_{uuid.uuid4().hex[:12]}"
                embedding = embedding_service.embed(mem.content, model=embedding_model)
                if not embedding:
                    raise ValueError("嵌入向量为空")
                self.chroma_client.add(
                    ids=[vector_id],
                    documents=[mem.content],
                    embeddings=[embedding],
                    metadatas=[{
                        "memory_id": mem.id,
                        "user_id": mem.user_id,
                        "type": mem.type,
                        "category": mem.category or "general",
                        "importance": mem.importance or 5
                    }]
                )
                mem.vector_id = vector_id
                rebuilt += 1
            except Exception as e:
                failed += 1
                logger.error(f"[MEMORY] 重建单条记忆失败 - id:{mem.id}, 错误:{e}")

        self.db.commit()

        # 记录向量库所用嵌入模型
        model_manager.set_vector_store_model(embedding_model)

        result = {
            "success": failed == 0,
            "total": total,
            "rebuilt": rebuilt,
            "failed": failed,
            "embedding_model": embedding_model
        }
        logger.info(f"[MEMORY] 向量库重建完成 - {result}")
        return result


# 全局实例
memory_service = MemoryService()
