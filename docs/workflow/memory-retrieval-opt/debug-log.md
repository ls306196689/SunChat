# Debug Log - memory-retrieval-opt

## D-1 external-content FTS5 索引损坏(database disk image is malformed)
- 状态: resolved | 步骤2 | 2026-09-06
- 复现: fts_sync_upsert 对 external-content 表执行 `INSERT INTO memory_fts(memory_fts, rowid) VALUES('delete', ?)` → `sqlite3.DatabaseError: database disk image is malformed`,连续 upsert 后整表不可用。
- 假设1: 'delete' 命令要求提供"索引中当时写入的旧内容"做一致性校验;分词串由 Python 生成、与内容表原文不同,校验必炸 → 验证: 改独立 FTS5 表(memory_id UNINDEXED, tokens),先删后插 —— 通过,根因确认。
- 假设2(次生): 损坏的旧表被 CREATE ... IF NOT EXISTS 静默保留,新代码报 no such column: memory_id → 修复: init_fts 检测 pragma_table_info 无 memory_id 列则 DROP 重建(对真实存量库同样必要)。
- 回归: tests/test_fts_index.py 12 用例(命中/用户隔离/软删/ASCII数字/引号注入/upsert替换/bootstrap/降级);修复后全绿。

## D-2 search_memories 融合循环解包错误
- 状态: resolved | 步骤4 | 2026-09-06
- 复现: `ValueError: too many values to unpack (expected 2)` 于 memory_service.py search_memories。
- 定位: `for mid, rrf in weight_map:` 对 dict 迭代得到 key(单值),缺 `.items()`。一次修复。
- 回归: test_hybrid_search 双通道用例覆盖;另修正 test_rrf_merge_basic 用例自身断言错误(等势分数误判大小 → 用严格可区分排名),属测试设计缺陷非实现缺陷。修复后全量 145 passed。


## D-3 测试隔离击穿生产库(数据事故 occurred) + 跨模块泄漏连环
- 状态: resolved | 步骤5后评测期 | 2026-09-06
- 事故: 新测试用模块级 autouse fixture 与 conftest 同名 setup_test_environment → pytest 规则模块级覆盖 conftest, 但其 body 未 mock 环境变量(旧模块同样缺失, 属存量地雷)→ reset_engine 指向生产 sunchat.db, fresh_db fixture query(Memory).delete() 把真实 24 条记忆删除(会话/消息完好)。
- 处置: 用户确认从日志恢复; 结合 messages 表对话历史交叉验证身份/偏好事实, 重建 12 条(孙鹏飞/咖啡美式/辣椒/运动/马拉松配速520/Alicare股票等); 排除测试污染文本。
- 根因修复(5 层):
  1. sql_models._guard_pytest_real_db: PYTEST 运行中测试连接非 test_ DB 直接 RuntimeError(防再次打穿)。
  2. conftest 新增 session 级 global_test_env_isolation(不可被遮蔽专名) + module 级 module_isolated_env: 每模块独立 DB/Chroma 文件并统一建库。
  3. 全部模块自设 setup_* fixture 改为仅 init_db(不再删共享文件/改环境变量)。
  4. ChromaClient._get_client 运行时读 settings + path/inode 漂移检测 + SharedSystemClient.clear_system_cache() 清陈旧句柄(修 'unable to open database file'/'readonly database'); _get_collection 每次校验绑定。
  5. model_manager._config_path 改 property 运行时解析(测试不再覆盖真实 model_config.json)。
- 跨模块连锁泄漏排查记录(≤2 回合/问题, 逐个证据定位): readonly-db→chroma 系统缓存 unlink 句柄; no such table: memory_fts→init_db 未建 FTS 表(生产同样受益: 任何新库自带); 统计接口 500→ChromaClient 陈旧 collection 短路; test_fts_index.py 被自己一行 read-after-truncate 脚本清零→重建。
- 回归: 全量 148 passed/1 skip(顺序+随机多次); 守卫用例证明 pytest 中连真实库必抛 guard 错误。
