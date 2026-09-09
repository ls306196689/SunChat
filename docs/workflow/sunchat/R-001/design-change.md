# R-001 增量设计

需求: R-001 | 基线: baseline.md → memory-retrieval-opt/design/(2026-09-06) | 状态: draft r1

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| r1 | 2026-09-08 | 初稿 | - |

## 变更清单(相对基线)
| # | 动作 | 对象(模块/接口) | 内容 | 触发 FR | 关联历史 | 兼容性 |
|---|---|---|---|---|---|---|
| C1 | 新增 | 模块 weather-core(`core/weather.py`) | 天气意图识别城市提取、wttr.in j1 直查、中文化格式化 | FR-1/2/5 | 模式复制自既有 core/stock.py(预流程 S4 行情直查) | 纯新增 |
| C2 | 修改 | chat.ChatService.build_context 内部流程 | 搜索接入段前插入"天气直查优先"分支,命中跳过 chat_router/DDG;函数签名与返回结构不变 | FR-3 | 修改预流程 sunchat-opt/S4 搜索接入的内部时序 | 内部兼容(返回 sources 新增 wttr-in 类型,前端按列表渲染不需改) |
| C3 | 新增 | agent-tools.get_weather(LLM 可见工具) | function-calling 注册 `get_weather(city)`,内部调 weather-core | FR-4 | 新增注册表条目,既有工具不受影响 | 兼容 |

## 受影响模块新版设计
| 模块 | 新版文档 | 替换基线 |
|---|---|---|
| weather-core | R-001/modules/weather-core.md | (新增,无基线) |
| chat-direct-weather | R-001/modules/chat-direct-weather.md | memory-retrieval-opt/design/modules/chat-injection.md 的搜索接入节(C2 增量,基线其余不变) |

## 数据流(天气查询)
```
用户消息 → build_context
  ├─ 记忆注入(基线 M3/M4,不变)
  ├─ 行情直查(不变)
  ├─ [新] is_weather_query? → get_weather_context(city…)
  │        成功 → system_prompt+=实时数据, sources[0]=wttr-in, weather_hit=True
  │        失败 → weather_hit=False
  └─ weather_hit? 跳过路由/DDG : chat_router→DDG(基线不变)
Agent 路径: LLM tool_call get_weather(city) → execute_tool → core.weather
```
无循环依赖:weather-core 仅依赖 utils.logger + requests;chat/agent → weather-core 单向。

## 技术选型
- wttr.in(JSON j1):免 Key 免费,用户指定最简方案(D-001)。
- requests 同步调用:与 core/stock.py 同款,零新依赖。
- 不做缓存:个人低频,超时失败快速回退,引入缓存反而陈旧误导。

## 风险(同步 state.risks;四类逐查)
| id | 类别 | 描述 | 概率 | 影响 | 缓解 | 状态 |
|---|---|---|---|---|---|---|
| R-1 | 依赖 | wttr.in 公共服不稳定/限流,直查随机失败 | 中 | 中 | 失败→None→自动回退 DDG;10s 快速超时 | mitigated |
| R-2 | 技术 | wttr.in JSON 字段变更致解析失败 | 低 | 中 | 解析异常捕获→None;单测锁定字段契约 | mitigated |
| R-3 | 技术 | 天气关键词误命中,该搜索的问题错走直查 | 低 | 低 | 取不到城市/数据仍回退;关键词表保守 | mitigated |
| R-4 | 技术 | 实现先于门禁(迁移遗留),文档↔代码漂移 | 中 | 中 | execute 阶段逐 AC 校对+全量单测,漂移即修并记录 | open |
| R-5 | 性能 | 直查为同步 HTTP,最坏 10s×城市数 阻塞响应 | 低 | 低 | 城市数≤3、超时 10s、失败即弃;远低于 LLM 生成耗时 | mitigated |
| R-6 | 安全 | 城市名拼入 URL;无 Key 无凭据面 | 低 | 低 | quote() URL 编码;不接收 LLM 任意 URL;日志不打敏感 | mitigated |

## 可观测性约定
- `[WEATHER]` 前缀 WARNING:wttr.in HTTP 状态码失败/请求异常(含 city);DEBUG:字段解析失败(含 city+异常)。
- `[CHAT]` 天气直查失败(忽略)WARNING;sources 含 wttr-in 条目可溯源。

## 测试约定
- pytest(既有),命令 `cd backend && pytest tests/`;新增 tests/test_weather.py 离线 mock
  requests,覆盖对外接口全集(is_weather_query/_to_cities/get_weather_context/工具注册执行)
  与 AC-1~3;AC-4 实机 SSE 抽查单列(区分 mock/实机,沿用基线评测约定)。

## 不做清单
- 多日/逐小时预报、缓存、付费源适配层、前端天气卡片渲染。
