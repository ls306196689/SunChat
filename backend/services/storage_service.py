"""
SunChat Backend - Storage Consistency Service (M1)
SQLite↔Chroma 对账自愈、悬空 vector_id 修复、原子重建(断点续跑)、写入阈值。
"""
import json
import os
import uuid
from typing import Dict, List, Optional

from app.config import settings, DATA_DIR
from core.embedding import embedding_service
from core.model_manager import model_manager
from models.sql_models import DBSessionMixin, Memory
from utils.logger import logger

CKPT_PATH = str(DATA_DIR / "rebuild_ckpt.json")


def write_allowed(confidence: float, importance: int,
                  min_conf: float = None, min_import: int = None) -> bool:
    """宁缺毋滥写入判定(D-004):低于阈值不入库。"""
    min_conf = settings.MEMORY_WRITE_MIN_CONFIDENCE if min_conf is None else min_conf
    min_import = settings.MEMORY_WRITE_MIN_IMPORTANCE if min_import is None else min_import
    try:
        return float(confidence) >= float(min_conf) and int(importance) >= int(min_import)
    except (TypeError, ValueError):
        return False


class StorageService(DBSessionMixin):

    def reconcile(self, dry_run: bool = False) -> Dict:
        """对账 SQLite 活跃记忆 vs Chroma 覆盖,修复 missing/dangling。

        维度守卫: 集合记录的嵌入模型与当前解析模型不一致 → 不补(应走 rebuild),
        防止两种向量混库(R-1)。
        """
        model = model_manager.resolve_embedding_model()
        result = {"checked": 0, "missing": 0, "dangling": 0,
                  "repaired": 0, "failed": 0, "drift": False}

        memories = (self.db.query(Memory)
                    .filter(Memory.is_active == True).all())  # noqa: E712
        result["checked"] = len(memories)

        vec_ids = [m.vector_id for m in memories if m.vector_id]
        existing = memory_service_chroma.has_ids(vec_ids)

        col_model = memory_service_chroma.collection_model()
        if col_model and col_model != model:
            logger.warning(f"[RECONCILE] 集合模型({col_model}) != 当前({model}), 跳过修复, 需重建向量库")
            result["drift"] = True
            result["missing"] = sum(1 for m in memories if not m.vector_id)
            result["dangling"] = sum(1 for m in memories if m.vector_id and m.vector_id not in existing)
            return result

        needs: List = []
        for m in memories:
            if not m.vector_id:
                result["missing"] += 1
                needs.append(m)
            elif m.vector_id not in existing:
                result["dangling"] += 1
                m.vector_id = None
                needs.append(m)

        if needs and not dry_run:
            self.db.commit()
            for m in needs:
                if self._embed_and_store(m):
                    result["repaired"] += 1
                else:
                    result["failed"] += 1

        result["drift"] = bool(result["missing"] or result["dangling"])
        logger.info(f"[RECONCILE] {result}")
        if not dry_run:
            self.db.commit()
        return result

    def ensure_vector(self, memory_id: str, content: str, user_id: int,
                      memory_type: str = "semantic", category: str = None,
                      importance: int = 5) -> Optional[str]:
        """生成向量写 Chroma, 返回 vector_id; 失败返回 None(调用方必须落 None, 禁止悬空 id)。"""
        try:
            embedding = embedding_service.embed(content)
            if not embedding:
                raise ValueError("嵌入向量为空")
            vector_id = f"vec_{uuid.uuid4().hex[:12]}"
            memory_service_chroma.add(
                ids=[vector_id], documents=[content], embeddings=[embedding],
                metadatas=[{"memory_id": memory_id, "user_id": user_id,
                            "type": memory_type, "category": category or "general",
                            "importance": importance}])
            return vector_id
        except Exception as e:
            logger.error(f"[STORAGE] ensure_vector 失败 - memory_id:{memory_id}: {e}")
            return None

    def _embed_and_store(self, memory: Memory) -> bool:
        vid = self.ensure_vector(memory.id, memory.content, memory.user_id,
                                 memory.type, memory.category, memory.importance or 5)
        if vid:
            memory.vector_id = vid
            return True
        return False

    # ==================== 原子重建 ====================

    def rebuild(self, resume: bool = True) -> Dict:
        """全量重嵌入。逐条写主集合并即时提交 vector_id(成功才落, 天然断点);
        checkpoint 文件记录进度, 单条失败计入 failed 不中断。"""
        embedding_model = model_manager.resolve_embedding_model()
        memories = (self.db.query(Memory)
                    .filter(Memory.is_active == True).all())  # noqa: E712
        total = len(memories)

        done_ids = set()
        if resume and os.path.exists(CKPT_PATH):
            try:
                with open(CKPT_PATH, "r", encoding="utf-8") as f:
                    ckpt = json.load(f)
                if ckpt.get("model") == embedding_model:
                    done_ids = set(ckpt.get("done_ids", []))
            except Exception:
                pass

        # 与目标模型不一致 → 清空集合重灌(R-1: 混库禁止)
        col_model = memory_service_chroma.collection_model()
        if col_model and col_model != embedding_model:
            logger.info(f"[REBUILD] 嵌入模型变更 {col_model} -> {embedding_model}, 清空集合")
            memory_service_chroma.recreate(embedding_model=embedding_model)
            done_ids = set()
        elif not col_model:
            memory_service_chroma.recreate(embedding_model=embedding_model)

        rebuilt = 0
        failed = 0
        ckpt_ids = list(done_ids)
        for mem in memories:
            if mem.id in done_ids:
                continue
            try:
                if mem.vector_id:
                    try:
                        memory_service_chroma.delete([mem.vector_id])
                    except Exception:
                        pass
                vid = self.ensure_vector(mem.id, mem.content, mem.user_id,
                                         mem.type, mem.category,
                                         mem.importance or 5)
                if not vid:
                    raise RuntimeError("ensure_vector 返回 None")
                mem.vector_id = vid
                self.db.commit()
                rebuilt += 1
                ckpt_ids.append(mem.id)
                self._write_ckpt(embedding_model, ckpt_ids)
            except Exception as e:
                failed += 1
                self.db.rollback()
                logger.error(f"[REBUILD] 单条失败 - id:{mem.id}: {e}")

        if failed == 0 and os.path.exists(CKPT_PATH):
            try:
                os.remove(CKPT_PATH)
            except OSError:
                pass

        model_manager.set_vector_store_model(embedding_model)
        result = {"success": failed == 0, "total": total, "rebuilt": rebuilt,
                  "failed": failed, "embedding_model": embedding_model}
        logger.info(f"[REBUILD] 完成 - {result}")
        return result

    def _write_ckpt(self, model: str, done_ids: List[str]) -> None:
        try:
            with open(CKPT_PATH, "w", encoding="utf-8") as f:
                json.dump({"model": model, "done_ids": done_ids}, f)
        except OSError as e:
            logger.warning(f"[REBUILD] checkpoint 写入失败: {e}")


# 延迟引用避免与 memory_service 循环 import
from services.memory_service import memory_service as _memory_service  # noqa: E402

memory_service_chroma = _memory_service.chroma_client
storage_service = StorageService()
