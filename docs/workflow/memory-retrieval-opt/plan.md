# memory-retrieval-opt 执行计划

状态: draft | 日期: 2026-09-06

## 步骤表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 环境准备:ollama pull bge-m3 + config 新增全部开关/阈值项(写入阈值、检索权重、topn、EMBEDDING_MODEL 默认 bge-m3) | config | design/overview.md, design/modules/storage-consistency.md §1 | backend/app/config.py diff;验证: `python -c "from app.config import settings; assert settings.MEMORY_WRITE_MIN_CONFIDENCE==0.6"`;pull 成功以 `ollama list` 含 bge-m3 为证 | R-1 |
| 2 | FTS 通道:core/fts_index.py(建表/触发器/fts_search/bootstrap/能力探测降级) | M2 | design/overview.md, design/modules/fts-index.md | core/fts_index.py + tests/test_fts_index.py;验证: `pytest tests/test_fts_index.py -q`(全绿, 内存库真跑 FTS5: 中文短语命中、软删同步、注入转义、<3字 LIKE 降级、FTS_AVAILABLE=False 返回[]) | R-5 |
| 3 | 存储一致性:storage_service reconcile/ensure_vector_on_create/rebuild(临时集合原子替换+checkpoint)/write_allowed;create_memory/rebuild_vector_store 接线;stats 暴露 drift | M1 | design/modules/storage-consistency.md, design/modules/fts-index.md §1 | services/storage_service.py + memory_service 改造 + routes/memories(stats)、routes/models(rebuild) 接线 + tests/test_storage_consistency.py;验证: `pytest tests/test_storage_consistency.py tests/test_memory_service.py -q`(mock Chroma 制造缺向量→reconcile 后相等[AC-1];悬空 id→None 不悬空;write_allowed 边界;rebuild checkpoint 续跑) | R-1 高危→从严 |
| 4 | 混合检索:core/ranking.py(rrf+final_score)+ MemoryService.search_memories 升级(双通道/recall/阈值/反馈写回)+ search_memories_by_analysis 原文优先 | M3 | design/modules/hybrid-search.md, design/modules/fts-index.md §1 | core/ranking.py + memory_service diff + tests/test_hybrid_search.py;验证: `pytest tests/test_hybrid_search.py tests/test_memory_service.py -q`(RRF 手算用例、阈值截断、FTS降级纯向量、碎片词不再作唯查询、反馈更新可关) | R-2, R-4 |
| 5 | 对话注入统一:build_context 走 v2+top_k、user_input 兜底填充、删死代码 build_memory_context、注入日志 [CHAT] | M4 | design/modules/chat-injection.md, design/modules/hybrid-search.md §1 | chat_service diff + tests/test_chat_flow_optimization 增补;验证: `pytest tests/test_chat_flow_optimization.py tests/test_chat_service.py -q`(注入≤top_k、死代码删除 grep 断言、日志字段) | R-2 |
| 6 | 离线基线冻结+golden set+评测脚本:M5 按设计实现;改造前代码先跑一次 before?→ 否(步骤已改代码),before 指标用 git stash 回退跑或依据步骤3/4前暂存点;实机执行 before(基于 HEAD 回退)/after 两份报告 | M5, eval | design/modules/eval.md | scripts/eval_memory.py + scripts/data/memory_golden.json(≥30条/6类各≥4)+ data/eval_report_before.json(由改造前 commit 运行)+ eval_report_after.json;验证: 脚本退出码 0 且两报告存在;`pytest tests -q` 全量仍绿;AC-2/AC-3 由报告数字判读(相对对比) | R-3, R-6 |
| 7 | 实机接线验证:bge-m3 生效启动→reconcile 补真实缺口→"我叫什么"类查询看 [CHAT]/[HYBRID] 日志证据;全量 pytest 终跑 | 集成 | design/overview.md §可观测性, plan.md | 日志片段存 docs/workflow/memory-retrieval-opt/e2e-evidence.md;验证: `pytest tests -q` 全绿[AC-5] + 实机日志命中证据[AC-4] | R-1, R-3 |

## 顺序与环
1→2→3→4→5→6→7,拓扑无环(M2 先于 M1 接线、M1 先于 M3,M3 先于 M4/M5)。

## 测试豁免声明
步骤 1 纯配置(断言 import 即验证);步骤 6 评测脚本依赖实机 Ollama,单测豁免理由见 overview 测试约定,其产物(报告)即验证物;golden set 数据文件为文档类。其余步骤全部含单测硬门禁。

## 风险映射
高危组合仅 R-1(中×高)→ 步骤 3 验证从严 + 步骤 1 先行演练(pull 成功即演练);R-3 高×中 → 步骤 6/7 实机项与离线项分离。
