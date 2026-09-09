# R-003 直查短路补全 + /health 搜索探活缓存

需求: R-003 | 类型: iteration(micro) | 状态: confirmed | 日期: 2026-09-08
> 门禁备注: 用户已授权"后续不要再让我确认,直接执行"(2026-09-08),各门禁按推荐项自动通过,confirmed_by=user(delegated)。

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-08 | 初稿(门禁按授权直通) | - |

## 一、需求
### 现象 / 动机
1. 行情直查命中后仍会走意图路由→DDG 搜索,权威数字已注入 system 却又叠加搜索摘要:
   多一次 DDG 请求(限流风险)+双源噪声。天气已有短路,行情没有。(依据 `analysis.md#A-1/C1`)
2. `/health` 每次实时调 `search_service.check_availability()` 真发 DDG 请求
   (实测 2.1s),前端健康面板轮询会持续打 DDG。(依据 `analysis.md#A-1/C3`)

### 期望行为
1. 行情或天气任一命中 → 跳过路由/DDG(与既有 weather_hit 短路同构);两者都未命中行为不变。
2. check_availability 结果缓存 60s:缓存新鲜期内直接返回缓存值,不发网络请求;
   过期后重测。? 语义不变:bool 可用性。

### 影响范围
- 文件: `backend/services/chat_service.py`、`backend/core/search.py`、`backend/tests/`(回归用例) — 共 3 文件
- 对外接口: build_context/health 响应结构不变(MUST);新依赖: 无

### 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | 行情命中时不再调用 search_svc.search_with_introduction | 新增单测 monkeypatch 断言未调用 |
| AC-2 | 行情/天气均未命中时走路由的行为不变(回归) | 既有用例 test_chat_flow_optimization + 新增断言仍调用 |
| AC-3 | check_availability 60s 内二次调用不发网络请求;缓存过期后重测 | 新增单测(mock DDGS 计数 + 拨时钟) |
| AC-4 | 全量回归 | `pytest tests/` 全绿 |

## 二、方案设计
### 改动点定位(附证据)
| 位置 | 证据 | 现行为 → 目标行为 |
|---|---|---|
| chat_service.py:274-301 | `[CODE] weather_hit 仅天气置位;decision 只按 weather_hit 短路` | 行情命中同样置位;`weather_hit or stock_hit → decision={"tool":None}` |
| core/search.py check_availability | `[CODE] 每次 ddgs.text("test") 真请求` | time.monotonic() 缓存 60s(bool+时间戳),新鲜期内返回缓存 |

### 修改思路
行情分支加 `stock_hit` 标志(与天气对称);短路条件改 `weather_hit or stock_hit`。
search.py 增加模块级 `_avail_cache=(monotonic_ts, bool)` 类属性,TTL 常量 60。

### 回归测试设计
- 新增 test_chat_flow_optimization 补 2 例:行情命中→无搜索调用;均未命中→仍搜索。
- 新增 test_search_service 补缓存 2 例:新鲜期不调网;过期调网且更新缓存。
- 既有 AC(stock/weather/search 注入)用例不动,全量跑防回归。

## 执行步骤(≤2)
| id | 目标 | 产出 + 验证方式 |
|---|---|---|
| 1 | 行情短路 + health 探活缓存 + 回归单测 | 3 文件修改;验证: `pytest tests/test_chat_flow_optimization.py tests/test_search_service.py tests/test_stock_quote.py tests/test_weather.py -q && pytest tests/ -q` 全绿 |

## 越界自检
- [x] 仍 ≤3 文件 [x] 未改对外接口(响应结构不变) [x] 无新架构决策 [x] 修复失败 <2 次

## 不做清单(明示)
- 行情/天气并行化:两意图同句罕见,串行最坏叠加概率低,引入线程复杂度不值(analysis A-1/C2 → 决策不做)。
- session_id 静默回退会话1(A-2)、日志轮转(A-3):行为变更面与收益不匹配,记基线观察项,后续需要另立需求。
