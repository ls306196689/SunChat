# M3 hybrid-search

状态: draft r1 | 2026-09-06

## 1. 对外接口
```python
# backend/services/memory_service.py(改造 MemoryService)
def search_memories(user_id, query, top_k=5, filters=None,
                    keywords: list[str] | None = None) -> list[dict]
# 升级为混合检索。返回元素在原结构上新增:
#   "final_score": float, "channels": ["vector","fts"]
# 流程见 §3。函数名/返回结构向后兼容(现有调用方 memories/routes 不破)。

def search_memories_by_analysis(user_id, analysis_result, top_k=5) -> list[dict]
# 改为: query=analysis_result.get("user_input") or " ".join(keywords)  # 原文优先
#       keywords=analysis_result.get("query_keywords")
# 调用 search_memories。修复"碎词拼接当查询串"问题(FR-4)。

# 新文件 backend/core/ranking.py
def rrf_merge(lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]
def final_score(sim: float, importance: int, age_days: float,
                access_count: int, w: dict) -> float
# w = {alpha:.7, beta:.15, gamma:.1, delta:.05}; decay=exp(-age_days/90)
# access 项 = min(access_count, 10)/10(封顶防富者愈富)
```
config 新增(默认值,评测集定参后可改):
```
MEMORY_VEC_TOPN: int = 10      # 向量通道召回数
MEMORY_FTS_TOPN: int = 10      # 关键词通道召回数
MEMORY_SIM_THRESHOLD: float = 0.3   # 注入前最低余弦相似度(R-2 保守起步)
MEMORY_FINAL_MIN_SCORE: float = 0.15
MEMORY_RANK_WEIGHTS: str = "0.7,0.15,0.1,0.05"
MEMORY_ACCESS_FEEDBACK: bool = True  # 命中后更新 access_count/accessed_at
```

## 2. 能力说明
- 提供:双通道召回+RRF+业务重排、原文优先查询构建、访问反馈写回、可配降级(FTS 关→纯向量;向量挂→FTS+旧 SQLite importance 回退保留)。
- 不提供:LLM rerank、查询改写、多跳检索。

## 3. 内部关键逻辑
1. 通道A(向量):现 Chroma top_k*2 逻辑保留(n=MEMORY_VEC_TOPN),产出 {memory_id: sim}。
2. 通道B(FTS):`fts_search(query, user_id, n=MEMORY_FTS_TOPN)` → {memory_id: rank}。
3. `rrf_merge` 两通道 id 列表得基础分 → 回 SQLite 批量取元数据(importance/created_at/access_count/content)。
4. `final_score` 重排;`sim < MEMORY_SIM_THRESHOLD` 的(仅向量通道有的)剔除;双通道都命中但 sim 缺失的按 0 处理但保留(靠 FTS 证据)。
5. 截断 top_k;`MEMORY_ACCESS_FEEDBACK` 开启 → 后台线程更新被注入记忆的 accessed_at/access_count+1(失败仅 DEBUG)。
6. 阈值/top_k/权重全部运行时读 settings,单测参数化覆盖。

## 4. 依赖
- M2 `core/fts_index.fts_search, FTS_AVAILABLE`(design/modules/fts-index.md)
- M1 `storage_service`(仅统计口径,无调用环)
- core.embedding / ChromaClient(现有)
