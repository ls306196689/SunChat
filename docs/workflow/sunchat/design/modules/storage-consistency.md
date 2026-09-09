# M1 storage-consistency

状态: draft r1 | 2026-09-06

## 1. 对外接口
```python
# backend/services/storage_service.py(新文件)
def reconcile(user_id: int | None = None, dry_run: bool = False) -> dict
# 对账 SQLite 活跃记忆 vs Chroma 覆盖。返回
# {"checked": int, "missing": int, "dangling": int, "repaired": int,
#  "failed": int, "drift": bool}
# missing=无向量/向量不在Chroma; dangling=vector_id指向Chroma中不存在的向量
# dry_run=True 只报告不修复。repair = 逐条 embed + chroma add + 更新 vector_id

def ensure_vector_on_create(content: str, meta: dict) -> str | None
# 供 create_memory 调用:返回 chroma vector_id;写入失败返回 None(调用方必须落 None,禁止悬空 id)

def rebuild(resume: bool = True) -> dict
# 替换现 memory_service.rebuild_vector_store:
# - 新集合 memories_new 逐条重嵌入写入(每条成功立即记录进度 checkpoint 文件)
# - 全部完成(含 failed 记录)后 delete 旧集合 + rename 原子替换
# - resume=True 时跳过 checkpoint 已完成 id
# 返回 {success,total,rebuilt,failed,embedding_model}

def write_allowed(confidence: float, importance: int,
                  min_conf: float, min_import: int) -> bool
# 纯函数:宁缺毋滥判定(D-004)
```
config 新增:
```
MEMORY_WRITE_MIN_CONFIDENCE: float = 0.6
MEMORY_WRITE_MIN_IMPORTANCE: int = 4
RECONCILE_ON_STARTUP: bool = True
EMBEDDING_MODEL: "bge-m3"(默认值变更)
```

## 2. 能力说明
- 提供:启动自检对账、悬空/缺失向量自愈、原子重建断点续跑、写入门槛。
- 不提供:知识库向量对账(KB 管道不在本需求)、自动定时任务(仅启动时+手动 API)。

## 3. 内部关键逻辑
- reconcile 用 Chroma `get(id=)` 批量校验 vector_id 存在性(不拉全库向量);missing 的重嵌入用当前 `model_manager.resolve_embedding_model()`。
- 维度守卫:reconcile 首条 embed 后与集合 metadata.embedding_model 比对,不一致 → 跳过修复并报告"需重建"(防止 bge-m3 与 nomic 混库,即 R-1)。
- rebuild checkpoint:`data/rebuild_ckpt.json {model, done_ids}`,模型名变化则作废重来。
- create_memory 改造:现有"Chroma 失败仍存 SQLite 并保留 vector_id"改为 vector_id=None + ERROR 日志(位置+memory_id+错误),由下次 reconcile 补偿。

## 4. 依赖
- `core.embedding.embedding_service.embed`(现有)
- `services.memory_service.ChromaClient`(改造:新增 `has(ids)`, `create_temp_collection`, `swap_collection`)
- M2 `fts-index.fts_sync_upsert/fts_sync_delete`(写路径钩子,文档 design/modules/fts-index.md)
