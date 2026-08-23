"""
SunChat Backend - Knowledge Base Service
支持文档上传、分块、向量化、存储和 RAG 查询
"""
import uuid
from typing import List, Dict, Optional
from datetime import datetime
import os

from app.config import settings
from core.embedding import embedding_service
from core.document_parser import document_parser
from models.sql_models import get_db, KBFile, KBChunk


class ChromaKnowledgeClient:
    """Chroma 知识库客户端"""

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

    def _get_collection(self, collection_name: str = "knowledge"):
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

    def query(self, query_embeddings: List[List[float]], n_results: int = 5) -> Dict:
        """查询相似向量"""
        collection = self._get_collection()
        return collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results
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
            self._get_client().delete_collection(name="knowledge")
            self._collection = None
        except Exception:
            pass


class KnowledgeService:
    """知识库服务"""

    def __init__(self):
        self.db = next(get_db())
        self.chroma_client = ChromaKnowledgeClient()

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

    def process_file(self, file_id: int, file_path: str, file_type: str) -> Dict:
        """
        处理文件（分块、向量化、存储）

        Args:
            file_id: 文件 ID
            file_path: 文件路径
            file_type: 文件类型

        Returns:
            处理结果
        """
        kb_file = self.db.query(KBFile).filter(KBFile.id == file_id).first()
        if not kb_file:
            return {"error": "File not found"}

        try:
            # 更新状态为 processing
            kb_file.status = "processing"
            self.db.commit()

            # 解析文档
            chunks = document_parser.parse(file_path, file_type)

            # 生成向量并存储到 Chroma
            vector_ids = []
            content_list = []
            metadata_list = []

            for i, chunk in enumerate(chunks):
                content = chunk["content"]
                # 生成嵌入向量
                try:
                    embedding = embedding_service.embed(content)
                except Exception as e:
                    print(f"Embedding error for chunk {i}: {e}")
                    # 使用空向量作为回退
                    embedding = [0.0] * 768  # 假设 768 维

                chunk_vector_id = f"kb_{file_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
                vector_ids.append(chunk_vector_id)
                content_list.append(content)
                metadata_list.append({
                    "file_id": file_id,
                    "chunk_index": i,
                    "page_number": chunk.get("page_number", 1),
                    "char_count": chunk.get("char_count", 0),
                    "word_count": chunk.get("word_count", 0)
                })

            # 写入 Chroma
            if content_list:
                try:
                    self.chroma_client.add(
                        ids=vector_ids,
                        documents=content_list,
                        embeddings=[embedding_service.embed(c) for c in content_list],
                        metadatas=metadata_list
                    )
                except Exception as e:
                    print(f"Chroma write error: {e}")
                    # 如果 Chroma 写入失败，继续使用 SQLite

            # 保存分块到 SQLite
            for i, chunk in enumerate(chunks):
                kb_chunk = KBChunk(
                    file_id=file_id,
                    chunk_index=i,
                    content=chunk["content"],
                    vector_id=vector_ids[i] if i < len(vector_ids) else "",
                    token_count=chunk.get("char_count", 0) // 4  # 粗略估计 token 数
                )
                self.db.add(kb_chunk)

            # 更新文件状态为 ready
            kb_file.status = "ready"
            kb_file.chunk_count = len(chunks)
            kb_file.vector_ids = vector_ids
            self.db.commit()

            return {
                "file_id": file_id,
                "status": "ready",
                "chunk_count": len(chunks),
                "message": f"成功处理 {len(chunks)} 个分块"
            }

        except Exception as e:
            # 更新状态为 failed
            kb_file.status = "failed"
            kb_file.error_message = str(e)
            self.db.commit()

            return {
                "file_id": file_id,
                "status": "failed",
                "error": str(e)
            }

    def retry_process_file(self, file_id: int) -> Dict:
        """重试处理失败的文件"""
        kb_file = self.db.query(KBFile).filter(KBFile.id == file_id).first()
        if not kb_file:
            return {"error": "File not found"}

        # 删除之前的分块
        self.db.query(KBChunk).filter(KBChunk.file_id == file_id).delete()

        # 重新处理
        return self.process_file(file_id, f"./data/uploads/{kb_file.filename}", kb_file.file_type)

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
                "error_message": f.error_message,
                "chunk_count": f.chunk_count,
                "created_at": f.created_at.isoformat()
            }
            for f in files
        ]

    def delete_file(self, file_id: int) -> bool:
        """删除文件"""
        kb_file = self.db.query(KBFile).filter(KBFile.id == file_id).first()
        if not kb_file:
            return False

        # 删除 Chroma 向量
        if kb_file.vector_ids:
            try:
                self.chroma_client.delete(kb_file.vector_ids)
            except Exception as e:
                print(f"Chroma delete error: {e}")

        # 删除分块
        self.db.query(KBChunk).filter(KBChunk.file_id == file_id).delete()

        # 删除文件记录
        self.db.delete(kb_file)
        self.db.commit()

        return True

    def search_knowledge(
        self,
        user_id: int,
        query: str,
        file_ids: List[int] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """
        搜索知识库

        Args:
            user_id: 用户 ID
            query: 搜索查询
            file_ids: 要搜索的文件 ID 列表（可选）
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        results = []

        try:
            # 生成查询向量
            query_embedding = embedding_service.embed(query)

            # 构建过滤条件
            filter_metadata = {"user_id": user_id}
            if file_ids:
                filter_metadata["file_id"] = {"$in": file_ids}

            # 查询 Chroma
            chroma_results = self.chroma_client.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2
            )

            # 处理结果
            chroma_ids = chroma_results.get("ids", [[]])[0]
            chroma_distances = chroma_results.get("distances", [[]])[0]
            chroma_metadatas = chroma_results.get("metadatas", [[]])[0]

            for i, chroma_id in enumerate(chroma_ids):
                if i >= len(chroma_metadatas):
                    continue

                metadata = chroma_metadatas[i]

                # 应用过滤
                if file_ids and metadata.get("file_id") not in file_ids:
                    continue

                # 将余弦距离转换为相似度
                distance = chroma_distances[i] if i < len(chroma_distances) else 0
                similarity = max(0, 1 - distance)

                # 获取文件信息
                kb_chunk = self.db.query(KBChunk).filter(KBChunk.id == metadata.get("chunk_index")).first()

                results.append({
                    "chunk_id": chroma_id,
                    "content": metadata.get("document", ""),
                    "file_id": metadata.get("file_id", 0),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "similarity": round(similarity, 4),
                    "metadata": metadata,
                    "created_at": datetime.now().isoformat() if kb_chunk is None else kb_chunk.created_at.isoformat() if hasattr(kb_chunk, 'created_at') else None
                })

            # 如果 Chroma 没有结果，回退到 SQLite
            if not results:
                results = self._search_knowledge_sqlite(user_id, query, file_ids, top_k)

        except Exception as e:
            print(f"Knowledge search error: {e}")
            results = self._search_knowledge_sqlite(user_id, query, file_ids, top_k)

        return results

    def _search_knowledge_sqlite(self, user_id: int, query: str,
                                  file_ids: List[int] = None,
                                  top_k: int = 5) -> List[Dict]:
        """SQLite 关键词搜索（作为回退方案）"""
        query = self.db.query(KBChunk).join(KBFile).filter(
            KBFile.user_id == user_id
        )

        if file_ids:
            query = query.filter(KBFile.id.in_(file_ids))

        # 简单的关键词匹配
        query = query.filter(
            KBChunk.content.like(f"%{query}%")
        )

        chunks = query.order_by(KBFile.created_at.desc()).limit(top_k).all()

        return [
            {
                "chunk_id": f"chunk_{c.id}",
                "content": c.content,
                "file_id": c.file_id,
                "chunk_index": c.chunk_index,
                "similarity": 0.5,  # 关键词匹配的默认相似度
                "metadata": {},
                "created_at": c.created_at.isoformat() if hasattr(c, 'created_at') else None
            }
            for c in chunks
        ]

    def qa(self, file_ids: List[int], query: str) -> Dict:
        """
        知识库问答（使用 RAG）

        Args:
            file_ids: 要搜索的文件 ID 列表
            query: 问题

        Returns:
            包含答案和来源的响应
        """
        # 搜索相关分块
        search_results = self.search_knowledge(
            user_id=1,  # 默认用户
            query=query,
            file_ids=file_ids,
            top_k=3
        )

        if not search_results:
            return {
                "answer": "未找到相关文档。",
                "sources": []
            }

        # 构建上下文
        context = "\n\n".join([r["content"] for r in search_results[:3]])

        # 构建 prompt
        prompt = f"""基于以下文档内容回答问题。

文档内容：
{context}

问题：{query}

请用中文回答，如果文档中没有相关信息，请说明。"""

        # 调用 LLM 生成答案
        try:
            from core.llm import ollama_service
            answer = ollama_service.generate(prompt, system="你是一个 helpful 的助手。请基于给定的文档内容回答问题。")

            return {
                "answer": answer,
                "sources": [
                    {
                        "file_id": r["file_id"],
                        "chunk_index": r["chunk_index"],
                        "relevance": r["similarity"],
                        "content_preview": r["content"][:200] + "..."
                    }
                    for r in search_results[:3]
                ]
            }
        except Exception as e:
            return {
                "answer": f"生成答案时出错: {e}",
                "sources": []
            }


# 全局实例
knowledge_service = KnowledgeService()
