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
from core import ranking as ranking_mod
from models.sql_models import DBSessionMixin, Memory, Emotion
from models.schemas import MemoryCreate, MemoryUpdate
from utils.logger import memory_logger, logger


class ChromaClient:
    """Chroma 向量数据库客户端（路径运行时解析，支持测试隔离配置切换）"""

    def __init__(self, persist_directory: str = None):
        self._fixed_dir = persist_directory
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self._bound_dir = None
        self._bound_ino = None
        self._client = None
        self._collection = None

    def _get_client(self):
        """获取 Chroma 客户端实例（配置路径变化, 或绑定目录被删/重建(inode 变)时自动
        重绑, 防测试污染/误删目录后句柄指向已 unlink 的只读旧库）"""
        import os
        import app.config as _cfg
        want = self._fixed_dir or str(_cfg.settings.CHROMA_PERSIST_DIR)
        try:
            cur_ino = os.stat(want).st_ino
        except OSError:
            cur_ino = None
        stale = (self._client is None or self._bound_dir != want
                 or self._bound_ino != cur_ino)
        if stale:
            import chromadb
            os.makedirs(want, exist_ok=True)
            # 关键: 丢弃可能缓存的、其 sqlite 文件已被删除的陈旧 system
            # （跨模块测试隔离时, 旧 path 的 system 仍缓存在 SharedSystemClient，
            # 复用即 "unable to open database file"）
            try:
                from chromadb.api.client import SharedSystemClient
                SharedSystemClient.clear_system_cache()
            except Exception:
                pass
            self._client = chromadb.PersistentClient(path=want)
            self.persist_directory = want
            self._bound_dir = want
            try:
                self._bound_ino = os.stat(want).st_ino
            except OSError:
                self._bound_ino = None
            self._collection = None
        return self._client

    def _get_collection(self, collection_name: str = "memories"):
        """获取集合（每次经 _get_client 校验绑定，路径/inode 变化时自动失效重建）"""
        self._get_client()  # 触发 stale 检测与重建（会置 _collection=None）
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
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

    def query(self, query_embeddings: List[List[float]], n_results: int = 5,
              include: List[str] = None, where: Dict = None) -> Dict:
        """查询相似向量（where 支持用户/类型隔离）"""
        collection = self._get_collection()
        if include is None:
            include = ["documents", "metadatas", "distances"]
        kwargs = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "include": include,
        }
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def delete(self, ids: List[str]):
        """删除向量"""
        collection = self._get_collection()
        collection.delete(ids=ids)

    def count(self) -> int:
        """获取向量数量"""
        collection = self._get_collection()
        return collection.count()

    def has_ids(self, ids: List[str]) -> set:
        """返回存在于此集合中的 id 子集（对账用）。"""
        if not ids:
            return set()
        try:
            collection = self._get_collection()
            got = collection.get(ids=ids, include=[])
            return set(got.get("ids", []) or [])
        except Exception as e:
            logger.warning(f"[CHROMA] has_ids 失败 - n:{len(ids)}: {e}")
            return set()

    def collection_model(self) -> str:
        """集合 metadata 记录的嵌入模型（无则空串）。"""
        try:
            meta = self._get_collection().metadata or {}
            return str(meta.get("embedding_model", "") or "")
        except Exception:
            return ""

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

        # FTS 关键词索引同步(提交后; 失败不影响主链路, 启动 bootstrap 兜底)
        try:
            from core.fts_index import fts_sync_upsert
            fts_sync_upsert(memory.id, memory.content)
        except Exception as e:
            logger.warning(f"[MEMORY] FTS 同步失败(忽略): {e}")

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
        filters: Dict = None,
        keywords: List[str] = None
    ) -> List[Dict]:
        """混合检索：Chroma 向量 + FTS5 关键词双通道召回 → RRF 融合 → 业务重排。

        返回结构向后兼容(memory_id/content/similarity/metadata), 新增:
          final_score: 融合排序分; channels: 命中的通道列表。
        向量通道故障时自动降级 FTS + SQLite importance 关键词回退。
        """
        logger.info(f"[MEMORY] 搜索记忆开始 - 用户:{user_id}, 查询:{query}, top_k:{top_k}")
        sim_map: Dict[str, float] = {}
        doc_map: Dict[str, Dict] = {}       # memory_id -> {content, metadata, similarity}
        vec_ids: List[str] = []
        vector_failed = False

        try:
            fused_query = query
            if keywords:
                fused_query = f"{query} {' '.join(keywords[:5])}" if query else " ".join(keywords[:5])
            query_embedding = embedding_service.embed(fused_query)

            conditions = [{"user_id": user_id}]
            if filters:
                if filters.get("type"):
                    conditions.append({"type": filters["type"]})
                if filters.get("category"):
                    conditions.append({"category": filters["category"]})
            where_filter = conditions[0] if len(conditions) == 1 else {"$and": conditions}

            chroma_results = self.chroma_client.query(
                query_embeddings=[query_embedding],
                n_results=max(settings.MEMORY_VEC_TOPN, top_k * 2),
                include=["documents", "metadatas", "distances"],
                where=where_filter,
            )

            chroma_ids = chroma_results.get("ids", [[]])[0]
            chroma_distances = chroma_results.get("distances", [[]])[0]
            chroma_metadatas = chroma_results.get("metadatas", [[]])[0]
            chroma_documents = chroma_results.get("documents", [[]])[0]

            for i in range(len(chroma_ids)):
                metadata = chroma_metadatas[i] if i < len(chroma_metadatas) else {}
                content = (chroma_documents[i] if i < len(chroma_documents)
                           else metadata.get("document", ""))
                if filters:
                    if filters.get("type") and metadata.get("type") != filters["type"]:
                        continue
                    if filters.get("category") and metadata.get("category") != filters["category"]:
                        continue
                distance = chroma_distances[i] if i < len(chroma_distances) else 0
                mid = metadata.get("memory_id", chroma_ids[i])
                sim_map[mid] = max(0.0, 1 - float(distance))
                doc_map[mid] = {"content": content, "metadata": metadata}
                vec_ids.append(mid)
        except Exception as e:
            vector_failed = True
            logger.error(f"[MEMORY] 向量通道失败(降级 FTS+关键词回退) - 错误:{e}")

        # FTS 关键词通道
        fts_ids: List[str] = []
        try:
            from core.fts_index import fts_search
            fts_full = query if not keywords else f"{query} {' '.join(keywords[:5])}"
            fts_ids = [mid for mid, _ in fts_search(fts_full, user_id,
                                                    n=settings.MEMORY_FTS_TOPN)]
        except Exception as e:
            logger.warning(f"[MEMORY] FTS 通道异常(忽略): {e}")

        if not vec_ids and not fts_ids:
            results = self._search_memories_sqlite(user_id, query, top_k, filters)
            logger.info(f"[MEMORY] 双通道无结果, SQLite importance 回退 - 结果数:{len(results)}")
            return results

        # RRF 融合 + SQLite 元数据补全
        merged = ranking_mod.rrf_merge([l for l in (vec_ids, fts_ids) if l])
        candidates = [mid for mid, _ in merged[:top_k * 3]]
        rows = {}
        if candidates:
            mems = (self.db.query(Memory)
                    .filter(Memory.id.in_(candidates), Memory.is_active == True)  # noqa: E712
                    .all())
            rows = {m.id: m for m in mems}

        weight_map = dict(merged)
        results: List[Dict] = []
        for mid, _rrf in weight_map.items():
            mem = rows.get(mid)
            if mem is None:
                continue
            sim = sim_map.get(mid, 0.0)
            channels = []
            if mid in sim_map:
                channels.append("vector")
            if mid in fts_ids:
                channels.append("fts")
            # 阈值: 向量命中且低相似且无 FTS 佐证 → 剔除(R-2: 阈值起步保守)
            if "vector" in channels and "fts" not in channels and sim < settings.MEMORY_SIM_THRESHOLD:
                continue
            age_days = ((datetime.now() - mem.created_at).total_seconds() / 86400.0
                        if mem.created_at else 0.0)
            fs = ranking_mod.final_score(sim, mem.importance or 5, age_days,
                                         mem.access_count or 0)
            if fs < settings.MEMORY_FINAL_MIN_SCORE:
                continue
            results.append({
                "memory_id": mid,
                "content": mem.content,
                "similarity": round(sim, 4),
                "final_score": round(fs, 4),
                "channels": channels,
                "metadata": doc_map.get(mid, {}).get("metadata") or {
                    "type": mem.type, "category": mem.category or "general",
                    "importance": mem.importance},
            })

        results.sort(key=lambda r: r["final_score"], reverse=True)
        results = results[:top_k]

        if settings.MEMORY_ACCESS_FEEDBACK and results:
            self._touch_accessed([r["memory_id"] for r in results])

        logger.info(f"[HYBRID] 检索完成 vec:{len(vec_ids)} fts:{len(fts_ids)} "
                    f"注入:{len(results)} top1_score:"
                    f"{results[0]['final_score'] if results else '-'}")
        return results

    def _touch_accessed(self, memory_ids: List[str]) -> None:
        """访问反馈: accessed_count+1, accessed_at=now(同步, 失败仅 DEBUG)。"""
        try:
            (self.db.query(Memory)
                 .filter(Memory.id.in_(memory_ids))
                 .update({Memory.access_count: Memory.access_count + 1,
                          Memory.accessed_at: datetime.now()},
                         synchronize_session=False))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.debug(f"[MEMORY] 访问反馈更新失败(忽略): {e}")


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

        try:
            from core.fts_index import fts_sync_upsert
            fts_sync_upsert(memory.id, memory.content)
        except Exception as e:
            logger.warning(f"[MEMORY] FTS 同步失败(忽略): {e}")

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

        try:
            from core.fts_index import fts_sync_delete
            fts_sync_delete(memory_id)
        except Exception as e:
            logger.warning(f"[MEMORY] FTS 删除同步失败(忽略): {e}")
        return True

    def list_memories(self, user_id: int, memory_type: str = None,
                      category: str = None, page: int = 1,
                      page_size: int = 20) -> Dict:
        """分页列出活跃记忆（支持类型/分类过滤，按更新时间倒序）"""
        q = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.is_active == True  # noqa: E712
        )
        if memory_type:
            q = q.filter(Memory.type == memory_type)
        if category:
            q = q.filter(Memory.category == category)

        total = q.count()
        items = (
            q.order_by(Memory.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "memories": [
                {
                    "id": m.id,
                    "type": m.type,
                    "category": m.category,
                    "content": m.content,
                    "importance": m.importance,
                    "confidence": m.confidence,
                    "tags": (m.extra_data or {}).get("tags", []),
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in items
            ],
        }

    def get_stats(self, user_id: int) -> Dict:
        """获取记忆统计"""
        total = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.is_active == True  # noqa: E712
        ).count()

        # 按类型统计
        from sqlalchemy import func
        type_counts = self.db.query(Memory.type, func.count(Memory.id)).filter(
            Memory.user_id == user_id,
            Memory.is_active == True  # noqa: E712
        ).group_by(Memory.type).all()

        # 按分类统计
        category_counts = self.db.query(Memory.category, func.count(Memory.id)).filter(
            Memory.user_id == user_id,
            Memory.is_active == True,  # noqa: E712
            Memory.category != None
        ).group_by(Memory.category).all()

        avg_conf = self.db.query(func.avg(Memory.confidence)).filter(
            Memory.user_id == user_id,
            Memory.is_active == True  # noqa: E712
        ).scalar()

        return {
            "total_count": total,
            "by_type": {k: v for k, v in type_counts},
            "by_category": {k: v for k, v in category_counts},
            "avg_confidence": round(float(avg_conf), 4) if avg_conf else 0.0,
            "chroma_collection_size": self.chroma_client.count(),
        }

    def get_drift(self) -> Dict:
        """SQLite 活跃记忆 vs Chroma 向量的覆盖缺口统计（只读, 供 stats 前端展示）。"""
        from sqlalchemy import func
        missing = self.db.query(func.count(Memory.id)).filter(
            Memory.is_active == True,  # noqa: E712
            (Memory.vector_id == None) | (Memory.vector_id == "")  # noqa: E711
        ).scalar() or 0
        total_vec = self.chroma_client.count()
        return {"vector_missing": int(missing), "chroma_size": int(total_vec),
                "drift": bool(missing)}

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
        query_keywords = analysis_result.get("query_keywords", []) or []

        # FR-4: 原始用户输入为主查询串, keywords 仅作辅助(不再碎词拼接成唯一查询)
        query_text = analysis_result.get("user_input", "")

        logger.info(f"[MEMORY] 根据分析结果查询记忆 - 用户:{user_id}, 关键词:{query_keywords}, "
                    f"主查询:{query_text[:50]}")

        # 注意：不用 recommended_memory_types 做 category 过滤——
        # 提取侧落库的 category（general/preference/...）与路由推荐类型（person/event/...）
        # 是两套分类法，硬过滤会把正确结果清零（如"我叫什么"推荐 person，
        # 但记忆存的是 general）。召回交给混合检索(向量+FTS)。
        results = self.search_memories(
            user_id=user_id,
            query=query_text,
            top_k=top_k,
            filters=None,
            keywords=query_keywords,
        )

        logger.info(f"[MEMORY] 根据分析结果查询完成 - 结果数:{len(results)}")
        return results

    def update_or_create_memory(self, user_id: int, content: str, memory_type: str = "semantic",
                                 category: str = None, importance: int = 5,
                                 confidence: float = 0.5) -> Dict:
        """
        更新或创建记忆 - 如果存在冲突的记忆则更新，否则创建新记忆

        写入阈值(D-004 宁缺毋滥): confidence/importance 低于 config 阈值直接拒绝入库。

        Args:
            user_id: 用户ID
            content: 记忆内容
            memory_type: 记忆类型
            category: 记忆分类
            importance: 重要性
            confidence: 提取置信度(来自 memory_extractor)

        Returns:
            记忆信息; 被阈值拒绝时 {"action": "rejected", "reason": ...}
        """
        from services.storage_service import write_allowed
        if not write_allowed(confidence, importance):
            logger.info(f"[MEMORY] 低于写入阈值, 拒绝入库 - conf:{confidence}, imp:{importance}, "
                        f"content:{content[:40]}")
            return {"action": "rejected",
                    "reason": f"confidence<{settings.MEMORY_WRITE_MIN_CONFIDENCE} "
                              f"or importance<{settings.MEMORY_WRITE_MIN_IMPORTANCE}"}

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
                logger.info(f"[MEMORY] 发现相似记忆，以新为准更新 - 相似度:{similarity}")
                existing = self.db.query(Memory).filter(
                    Memory.id == mem.get("memory_id"),
                    Memory.user_id == user_id,
                ).first()
                if existing:
                    # 冲突以最新内容为准：更新 content 并重新嵌入向量
                    existing.content = content
                    if importance > existing.importance:
                        existing.importance = importance
                    existing.confidence = min(1.0, existing.confidence + 0.1)

                    try:
                        # 先生成新向量成功, 再删旧向量(顺序防丢)
                        from services.storage_service import storage_service
                        new_vector_id = storage_service.ensure_vector(
                            existing.id, content, user_id,
                            existing.type, existing.category, existing.importance)
                        if not new_vector_id:
                            raise RuntimeError("ensure_vector 返回 None")
                        if existing.vector_id:
                            try:
                                self.chroma_client.delete([existing.vector_id])
                            except Exception:
                                pass
                        existing.vector_id = new_vector_id
                    except Exception as e:
                        logger.warning(f"[MEMORY] 冲突更新重嵌入失败（保留旧向量）: {e}")

                    self.db.commit()
                    self.db.refresh(existing)

                    try:
                        from core.fts_index import fts_sync_upsert
                        fts_sync_upsert(existing.id, content)
                    except Exception as e:
                        logger.warning(f"[MEMORY] FTS 同步失败(忽略): {e}")

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
