# R-005 session 契约收口(GET 端点 400+分页限幅+Agent 非法 id 400)

需求: R-005 | 类型: bugfix(micro) | 状态: confirmed | 日期: 2026-09-11

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-11 | 初稿 | 全面体检(R-004 遗留同型端点) |

## 一、需求
### 现象 / 动机
R-004 确立"非法 session_id 一律 400、禁止静默降级"契约,但仅收口 POST
/chat/messages 与 /chat/stream 两端点。体检复现三处同型缺口(`analysis.md#A-1`):
`GET /chat/sessions/{id}/messages` 非法 id → 500;分页 page=0 → 负 offset 仍 200;
`POST /chat/agent` 非空非法 session_id → 200 但历史静默丢失。契约不一致会误导
前端并掩盖数据丢失。

### 根因(缺陷类必填,MUST 引用 analysis.md#A-n)
R-004 治理范围仅声明两聊天端点,GET/agent 同型端点未覆盖(实现违约,非文档过时)
— 依据: `analysis.md#A-1`(C1-C4,[REQ][GIT][CODE][RUN] 10 项证据)

### 期望行为
1. `GET /chat/sessions/{id}/messages` 非法 id → 400 "session_id 非法"(复用
   `_resolve_session_id`),service 不被调用;合法数字 id 行为不变(含不存在→现状)。
2. 分页参数声明式限幅:`page ≥ 1`、`page_size ∈ [1,100]`,越界 → 422(FastAPI 原生
   Query 校验,D-101:不手工 400,取标准校验语义与 OpenAPI 文档收益);service 不被调用。
3. `POST /chat/agent`:session_id **非空且非法** → 400;**空/缺省** → 维持无会话
   模式(既有合法语义,保留);合法数字 → 落库回归不变。
4. 死代码清理:删除 `backend/app/dependencies.py`、`backend/app/api/v1/routes/deps.py`、
   空目录 `backend/app/v1/`(全仓 grep 0 引用)。

### 影响范围
- 文件: `app/api/v1/routes/chat.py`、`app/api/v1/routes/agent.py`、
  `tests/test_session_contract.py`(新增) | 删除: 3 个零引用死工件(无行为影响)
- 对外接口: 合法请求行为不变(MUST);仅非法输入由 500/静默 改 400/422
- 新依赖: 无

### 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | GET 非法 id → 400 且 service 未被调用 | TestClient + spy(先 red 后修绿) |
| AC-2 | GET page=0/page_size=101 → 422 且 service 未被调用 | TestClient |
| AC-3 | agent 非空非法 id → 400;空 id → 200 无会话(回归);合法 → 落库(回归) | TestClient + spy |
| AC-4 | GET/agent 合法路径回归不变 | 同上 spy 断言 |
| AC-5 | 死文件删除后 import 与全量测试正常 | `python -c "import app.main"` + pytest |
| AC-6 | 全量回归 | `pytest tests/` 全绿 |

## 二、方案设计
### 改动点定位(附证据)
| 位置 | 证据 | 现行为 → 目标行为 |
|---|---|---|
| routes/chat.py:137-144 | `[CODE] int(session_id)` 无守卫 `[RUN] abc→500` | 复用 `_resolve_session_id` → 400 |
| routes/chat.py:138 | `[RUN] page=0→offset=-20 仍200` | `page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)` |
| routes/agent.py:36-38 | `[CODE] if ... and .isdigit():` `[RUN] abc→200不落库` | 非空非数字→400;空→None 无会话;数字→int |
| app/dependencies.py 等 | `[CODE] 全仓 grep "app.dependencies\|from .deps" 0 引用` | 删除 |

### 修改思路
GET 端点直接复用既有 `_resolve_session_id`(chat.py:27),分页改 FastAPI `Query`
声明式约束;agent 路由把静默条件拆为三分支(空=无会话、非法=400、合法=int)。
先写 `tests/test_session_contract.py` 断言目标行为(red),再改实现转绿。

### 回归测试设计
新增 test_session_contract.py 覆盖 AC-1~AC-4(spy 断言 service 调用面);
回归既有 test_session_validation.py(R-004 AC)与 test_agent.py 全量保持;
AC-6 全量 pytest。

## 执行步骤(≤2)
| id | 目标 | 产出 + 验证方式 |
|---|---|---|
| 1 | red test 先行 + chat/agent 契约修复 | tests/test_session_contract.py + 两路由改动;验证: `pytest tests/`(MUST 全绿) |
| 2 | 死文件清理 | 删 dependencies.py/routes/deps.py/app/v1/;验证: `import app.main` + `pytest tests/` |

## 越界自检(执行中每轮核对)
- [x] 仍 ≤3 文件(行为改动 2 + 测试 1;删除零逻辑)? [x] 未改对外接口(合法路径)?
- [x] 无新架构决策? [x] 修复失败 <2 次?

## 决策
- [D-101] 2026-09-11 分页校验语义: 采用 FastAPI Query(ge/le)→422,不手工统一 400;
  理由: 声明式零额外代码、OpenAPI 自动文档;session_id 保持 400 与 R-004 契约对齐。
- [D-102] 2026-09-11 agent 空 session_id 保留无会话模式: 属既有合法语义(无状态
  Agent 调用),仅"非空非法"才 400,避免破坏现用法。

## 归档结果(2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | test_get_invalid_session_400:abc→400 且 spy 空(修复前 red:500) |
| AC-2 | 通过 | test_get_page_zero_422 / test_get_page_size_over_limit_422:422 且 spy 空 |
| AC-3 | 通过 | agent abc→400 不落库(原 200 静默);空/缺省→200 无会话(D-102) |
| AC-4 | 通过 | GET 7→200 spy session_id==7;agent "9"→save(user,9)+(asst,9);边界 1/100 合法 |
| AC-5 | 通过 | 删 dependencies.py/routes/deps.py/app/v1 后 `import app.main` OK |
| AC-6 | 通过 | `pytest tests/` → **179 passed, 1 skipped**(基线 170+9 新增);R-004 既有用例无回归 |

风险终态:R-1 mitigated(前端 grep 仅真实 id;空 id 放行)、R-2 closed(全量无断言冲突)。
commit 范围:fix(R-005/step-1) + chore(R-005/step-2) + docs(R-005) archive。
基线:未触碰 design/ 在册模块行为(session 契约为路由面,R-004 先例不回写)。
越界自检:改动 ≤3 文件、未改合法路径接口、无新架构决策——micro 通道守界。

