需求: R-006 | plan(标准 iteration,门禁直通)

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 基线核对+行情去重+短超时+探活缓存 实现 | search_service/chat_service/llm/memory_router/memory_extractor/model_manager/config | R-006/{requirements,design-change,analysis}.md + 上述文件 | 代码改动 + `tests/test_hotpath_opt.py`(AC-1~4 单测);验证: `pytest tests/` 全绿 | R-1,R-2,R-3 |

> micro→标准说明:涉及 7 文件 >3,走标准 iteration;实现集中单次提交
> (一步=一次可独立验证切片),步骤数 1 ≤ 门禁要求。
> 测试约定(基线 overview):pytest + monkeypatch spy,全量绿为硬门禁。

## 总结节(验收归档 2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | test_stock_fail_path_calls_api_once(spy 计数=1);独立调用默认不变+显式传入跳过API |
| AC-2 | 通过 | test_memory_router/extractor_uses_light_timeout(timeout=20 断言);test_generate_default_timeout_none 主路径不变 |
| AC-3 | 通过 | test_is_available_cached_within_ttl(3调用1实探);test_failure_result_also_cached(宕机0.000s返回);test_invalidate_forces_reprobe |
| AC-4 | 通过 | test_health_contract 六字段齐全 |
| AC-5 | 通过 | `pytest tests/` → **190 passed, 1 skipped**(基线 179+11 新增) |

风险终态:R-1 closed(回退路径有单测,超时 config 可调)、R-2 closed(set_*失效+TTL短)、
R-3 closed(独立调用方默认行为回归绿)。
commit:c02805e8 perf(R-006/step-1) + docs(R-006) archive。
基线回写:未触碰 design/ 在册模块对外接口(与 R-003 先例一致,不回写)。
遗留候选:P2 搜索归纳+主生成二次 LLM 合并(D-202,涉及回答质量权衡,留待后续需求)。
