# R-002 Agent 工具框架无条件注入 user_id 导致无该形参的工具必然失败

需求: R-002 | 类型: bugfix | 状态: confirmed | 日期: 2026-09-08

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-08 | 初稿 | - |
| v1.1 | 2026-09-08 | change_confirmed | 门禁 |

## 一、需求
### 现象 / 动机
Agent function-calling 路径下调用 `web_search` 必然失败:
`web_search() got an unexpected keyword argument 'user_id'`。这是用户最初报告
"查询天气失败"的多个成因之一(R-001 解决天气数据源侧,本需求修框架侧)。

### 根因(缺陷类必填)
`execute_tool` 为防越权**无条件**注入 `args["user_id"]`,且白名单把 `user_id` 恒放行;
`web_search` 签名无 user_id → TypeError。见 `analysis.md#A-1`(A-1/C1,C2)。

### 期望行为
仅当目标工具签名接受 user_id 时才注入(memory_search/memory_create/knowledge_search
防越权语义不变);不接受的工具(web_search/get_weather)不注入、正常执行。
LLM 传入的 user_id 仍一律丢弃,防越权不回退。

### 影响范围
- 文件: `backend/core/agent/tools.py`(修改) | 对外接口: execute_tool 签名不变(MUST) | 新依赖: 无(仅标准库 inspect)

### 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | execute_tool('web_search',{...,"user_id":999}) 成功且 LLM 伪造 user_id 被丢弃 | `pytest tests/test_weather.py::TestAgentTool -k no_user_id` + `pytest tests/test_agent* -q`(既有) |
| AC-2 | 带 user_id 形参工具(memory_search)仍强制注入会话 user_id,防越权不回退 | 同上(既有用例)+新用例断言注入值 |
| AC-3 | 全量回归 | `pytest tests/` 全绿 |

## 二、方案设计
### 改动点定位(附证据)
| 位置 | 证据 | 现行为 → 目标行为 |
|---|---|---|
| tools.py execute_tool(HEAD:152) | `[CODE] args["user_id"] = user_id or ...` 无条件 | 注入前用 `inspect.signature` 判断工具是否接受 user_id |
| tools.py 顶部 import | 无 inspect | 增加 `import inspect` |

### 修改思路
pop 掉 LLM 传入的 user_id 后,检查 `td.function` 签名:`user_id` 在参数表中才注入
`user_id or settings.LOCAL_USER_ID`。防越权语义(pop+强制值)在注入型工具上保持原样。

### 回归测试设计
- 新增: web_search 型(无形参)/memory_search 型(有形参,断言注入值覆盖)/未知工具报错路径。
- 既有: test_agent_tools/agent 路由相关用例全量跑,确认无行为回归。

## 执行步骤(≤2)
| id | 目标 | 产出 + 验证方式 |
|---|---|---|
| 1 | execute_tool 注入条件化 + 回归单测 | tools.py 修改 + 测试;验证: `pytest tests/test_weather.py -q && pytest tests/ -q` 全绿 |

## 越界自检(执行中每轮核对)
- [x] 仍 ≤3 文件(1 文件+测试) [x] 未改对外接口 [x] 无新架构决策 [x] 修复失败 <2 次
> 任一失守 → 立即停止,escalated,state.escalated_from_micro=true,phase→expand。
