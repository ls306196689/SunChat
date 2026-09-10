需求: R-007 | 类型: iteration | 状态: 已确认 | 日期: 2026-09-11 | 版本: v1

# R-007 资源与数据层加固

## 1. 背景
全面体检(提案 C 组 P5/R4/P3,取证 `analysis.md#A-1`):全部表仅主键无索引,
数据增长后热查询全表扫描;记忆后台提取每条消息裸起线程无上限;天气/行情直查
无 TTL 缓存(同会话追问重复拉全量,多城串行最坏 30s)。

## 2. 与历史需求的关系
- 沿用 R-003 探活缓存(AVAIL_TTL)与 R-006(R-006 的 is_available 缓存同为该模式)
  的"结果级 TTL 缓存"语义,扩展到行情(60s)/天气(600s);
- R-001 天气直查/R-003 行情直查的对外函数签名与返回结构不变(仅内部加缓存);
- 不改 chat_service 对外接口(extract_memories_async 签名不变)。

## 3. 核心场景
- 用户连续追问"那明天呢/后天呢" → 现状:每问重新拉 wttr 全量 JSON(城市×10s);
  优化后:10 分钟内城市级命中直接复用。
- 60s 内重复问同一股价 → 行情缓存命中,不再打腾讯 API。
- Ollama 排队时用户连发 20 条消息 → 现状:20 个后台线程各持 300s 提取调用;
  优化后:2 worker + 队列 8,超出丢弃记 WARNING,主链路不受影响。
- 消息表 1 万行后取分页 → 现状全表扫描;优化后 (session_id, created_at) 索引扫描。

## 4. 功能点
- FR-1 DB 索引:模型 `index=True`(新库)+ `ensure_schema` 内
  `CREATE INDEX IF NOT EXISTS`(存量库幂等补齐)。索引列(仅热查询面,占位声明):
  messages(session_id, created_at)、chat_sessions(user_id)、
  memories(user_id, is_active)、kb_chunks(file_id)、search_history(user_id)。
- FR-2 提取线程池化:extract_memories_async 改 ThreadPoolExecutor(max_workers=2),
  在途上限 8(含排队),超限丢弃并 WARNING;_job 保留 reset_thread_session。
- FR-3 直查 TTL 缓存:行情结果缓存 60s(仅成功);天气城市级缓存 600s(仅成功);
  失败不缓存(下次重试)。函数签名与返回不变。

## 5. 边界与非目标
- 不做 alembic、不删既有数据/表;索引仅上述热列,不预防性滥建;
- 不做多城并行请求(缓存已消除重复请求,串行首查延迟由 10s 超时兜底,留作后续);
- search_history 30 天清理(C4 项)不在本需求,留后续候选。

## 6. 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | tmp 库 ensure_schema 后 `inspect.get_indexes` 五张表索引齐全;重复执行幂等无错 | pytest(tmp_path DB) |
| AC-2 | 并发提交 >8 个提取任务:pool 活跃 ≤2、丢弃有 WARNING、计数恢复、后续任务可继续;既有"后台提取不阻塞主链路"用例回归 | spy 单测 |
| AC-3 | 天气同(city)两次调用 requests.get 仅 1 次;TTL=0 立即重取;失败结果不入缓存 | mock 计数 |
| AC-4 | 行情同 symbols 60s 内第二次不打腾讯 API;失败不缓存 | mock 计数 |
| AC-5 | 全量回归 | `pytest tests/` 全绿 |

## 7. 风险
| id | 风险 | prob | impact | 缓解 |
|---|---|---|---|---|
| R-1 | 存量库启动时建索引一次性开销/短暂锁 | 低 | 低 | IF NOT EXISTS 幂等、SQLite 本地表量小、启动期一次 |
| R-2 | 队列满丢弃提取(记忆静默缺失) | 低 | 中 | WARNING 日志显式可查;上限/池可 config;主链路不损 |
| R-3 | 行情缓存最长 60s 旧价 | 中 | 低 | 对话场景可接受(用户明示追问多为同值);天气 600s 同理 |
| R-4 | 池线程复用致 thread-local DB Session 残留 | 中 | 中 | _job finally 保留 reset_thread_session(原设计语义) |
