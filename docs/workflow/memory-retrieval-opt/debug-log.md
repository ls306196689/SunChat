# Debug Log - memory-retrieval-opt

## D-1 external-content FTS5 索引损坏(database disk image is malformed)
- 状态: resolved | 步骤2 | 2026-09-06
- 复现: fts_sync_upsert 对 external-content 表执行 `INSERT INTO memory_fts(memory_fts, rowid) VALUES('delete', ?)` → `sqlite3.DatabaseError: database disk image is malformed`,连续 upsert 后整表不可用。
- 假设1: 'delete' 命令要求提供"索引中当时写入的旧内容"做一致性校验;分词串由 Python 生成、与内容表原文不同,校验必炸 → 验证: 改独立 FTS5 表(memory_id UNINDEXED, tokens),先删后插 —— 通过,根因确认。
- 假设2(次生): 损坏的旧表被 CREATE ... IF NOT EXISTS 静默保留,新代码报 no such column: memory_id → 修复: init_fts 检测 pragma_table_info 无 memory_id 列则 DROP 重建(对真实存量库同样必要)。
- 回归: tests/test_fts_index.py 12 用例(命中/用户隔离/软删/ASCII数字/引号注入/upsert替换/bootstrap/降级);修复后全绿。
