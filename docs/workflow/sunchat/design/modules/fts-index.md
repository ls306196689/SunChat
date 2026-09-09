# M2 fts-index

状态: draft r1 | 2026-09-06

## 1. 对外接口
```python
# backend/core/fts_index.py(新文件)
FTS_AVAILABLE: bool  # 启动探测结果

def init_fts() -> None
# 建 FTS5 external-content 影子表(幂等, 挂在现有 engine connect 钩子/启动时):
# CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
#   content, content='memories', content_rowid='rowid',
#   tokenize='trigram');
# 并建/替换 memories 的 INSERT/UPDATE/DELETE 触发器同步 fts 行
# (触发器仅同步 is_active=1 行;删除/软删同步删 fts)

def fts_search(query: str, user_id: int, n: int = 10) -> list[tuple[str, float]]
# 返回 [(memory_id, bm25_score_desc)]。实现:
# query 拆空白分词, 每词加引号做短语查询 OR 连接("张三" OR "股价"):
# trigram 下 ≥3字子串可命中,<3字中文词自动降级 LIKE 补查该词
# JOIN memories 过滤 user_id/is_active, bm25() 取负数转正分
# FTS_AVAILABLE=False 时返回 []

def fts_sync_upsert(memory_id: str) -> None   # 单条重建(供 reconcile/回填用)
def fts_bootstrap_from_sqlite() -> int        # 全量回填,返回同步行数
```

## 2. 能力说明
- 提供:中文子串级关键词检索、与 Memory 表最终一致的索引、能力探测降级。
- 不提供:分词器(jieba 等不引入)、词干化/同义词、拼音检索。

## 3. 内部关键逻辑
- 触发器与软删除:`AFTER UPDATE OF is_active ON memories WHEN NEW.is_active=0 → DELETE FROM memory_fts`;AFTER INSERT/UPDATE 同样只处理 is_active=1(条件触发器)。
- bm25() 返回负值(越小越优),统一 `-bm25()` 作正分。
- 短语引号包裹防 SQL 注入/操作符注入:词内 `"` 转义为 `""`。
- 启动 `init_fts` 若抛 OperationalError("no such module: fts5") → FTS_AVAILABLE=False + WARNING(R-5 降级);单测用内存库真跑 FTS。
- `fts_search` 的 trigram 子串 <3 字降级 LIKE:仅对短词生效,LIKE 结果并入同集合,score 给中位分。

## 4. 依赖
- 仅 `models.sql_models` engine/连接(标准 sqlite3 FTS5,环境已验证 3.45.3)
- 被依赖:M1(写钩子)、M3(检索通道)
