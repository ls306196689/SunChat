需求: R-007 | plan(标准 iteration,门禁总授权直通)

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 热列索引(模型+ensure_schema幂等)+提取有界池+天气/行情TTL缓存 | models/sql_models.py, services/chat_service.py, core/weather.py, core/stock.py | R-007/{requirements,design-change,analysis}.md + 上述文件 | 代码 + tests/test_resource_hardening.py(AC-1~4);验证: `pytest tests/` 全绿(含既有用例回归隔离) | R-1,R-2,R-3,R-4 |

> 步骤数 1,单步可独立验证。测试隔离教训:模块级 TTL 缓存需 autouse clear
> (test_weather/test_stock_quote 已补 fixture)。

## 总结节(验收归档 2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | test_hot_indexes_exist:五表索引 inspect 齐全;test_ensure_schema_idempotent 重复执行无错 |
| AC-2 | 通过 | test_pool_drops_over_limit:在途8受理/第9丢弃None/归零恢复;test_workers_bounded_2;失败后inflight归零 |
| AC-3 | 通过 | 天气两次调用requests.get仅1次;TTL=0即重取;失败不缓存(2次重试) |
| AC-4 | 通过 | 行情同symbols 60s内仅1次_fetch_tencent;失败不缓存 |
| AC-5 | 通过 | `pytest tests/` → **200 passed, 1 skipped**(基线 190+10 新增) |

风险终态:R-1 closed(IF NOT EXISTS幂等,本地小库);R-2 closed(WARNING可查,主链路零损);
R-3 closed(60s旧价对话场景可接受);R-4 closed(_job finally reset_thread_session保留,
池复用线程不泄漏Session)。
执行偏差记录:ensure_schema 曾顺手实现 search_history 清理(越界),已当即回退,
清理功能留后续独立需求(R-008 候选)。
隔离调试(debug D-1):新增缓存致 test_weather 3 失败 → 根因 模块级缓存跨用例污染,
修复 autouse clear_weather_cache/clear_stock_cache → 全绿(1回合,未超限)。
commit:136e63a0 perf(R-007/step-1) + docs(R-007) archive。
基线回写:未触碰 design/ 在册模块对外接口(索引/池/缓存均为内部实现,签名不变)。
