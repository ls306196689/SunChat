需求: R-007 | 增量设计(design-change) | 状态: 已确认 | 日期: 2026-09-11

相对基线 `design/`:无模块对外接口变化(索引=物理层、池=私有实现、缓存=函数内部),
与 R-003/R-006 同型,不回写基线模块文档。

## 改动 1:热列索引(FR-1)
- 模型层 `index=True`(新库 create_all 自动建):chat_sessions.user_id、
  messages.session_id、messages.created_at、memories.user_id、kb_chunks.file_id、
  search_history.user_id。
- `ensure_schema` 追加 `_HOT_INDEXES` 表驱动
  `CREATE INDEX IF NOT EXISTS`(存量库补齐,双保险幂等):
  `idx_messages_session_id_created_at(session_id,created_at)`、
  `idx_chat_sessions_user_id`、`idx_memories_user_id_is_active(user_id,is_active)`、
  `idx_kb_chunks_file_id`、`idx_search_history_user_id`。

## 改动 2:提取有界池(FR-2)
- `ChatService` 类属性 `_extract_workers=2 / _extract_max_inflight=8`,
  实例属性 `_extract_lock/_extract_inflight/_extract_pool`(惰性创建
  ThreadPoolExecutor,thread_name_prefix="memory-extractor")。
- `extract_memories_async` 签名不变:锁内计在途,超限 WARNING+返回 None(丢弃);
  否则 submit 并 +1;`_job` finally 中 reset_thread_session(原语义保留)且 −1。

## 改动 3:直查 TTL 缓存(FR-3)
- weather:`_CACHE_TTL=600`,`_city_cache: Dict[str,(mono_ts, text)]`+锁;
  `get_weather_context` 先查缓存(城市级),命中拼用;失败(异常/非200/解析空)
  不入缓存;`clear_weather_cache()` 测试钩子。
- stock:`_CACHE_TTL=60`,key=`tuple(symbols)`;同上语义;`clear_stock_cache()`。
- staleness 语义声明:TTL 内即使外部源故障仍返回旧值——对话场景可用性优先,
  与 R-003 DDG 探活缓存/R-006 探活缓存同型(有文档依据)。

## 测试隔离设计
模块级缓存 → test_weather/test_stock_quote 增 autouse fixture 前后清缓存;
新增 test_resource_hardening.py 全部自清。

## 决策
- [D-301] 索引仅热查询面(analysis A-1/C1 列出),不预防性滥建;composite
  (session_id,created_at) 匹配"按会话过滤+排序分页"单一最热查询。
- [D-302] 缓存仅成功入缓,失败不缓(重试优于staleness 放大);TTL 天气600s/行情60s。
- [D-303] 池丢弃策略=拒绝新任务+WARNING(而非阻塞主链路或无界排队)。
- [D-304] search_history 30天清理不并入本需求(范围纪律),留后续需求。
