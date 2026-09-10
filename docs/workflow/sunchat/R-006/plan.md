需求: R-006 | plan(标准 iteration,门禁直通)

| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 基线核对+行情去重+短超时+探活缓存 实现 | search_service/chat_service/llm/memory_router/memory_extractor/model_manager/config | R-006/{requirements,design-change,analysis}.md + 上述文件 | 代码改动 + `tests/test_hotpath_opt.py`(AC-1~4 单测);验证: `pytest tests/` 全绿 | R-1,R-2,R-3 |

> micro→标准说明:涉及 7 文件 >3,走标准 iteration;实现集中单次提交
> (一步=一次可独立验证切片),步骤数 1 ≤ 门禁要求。
> 测试约定(基线 overview):pytest + monkeypatch spy,全量绿为硬门禁。
