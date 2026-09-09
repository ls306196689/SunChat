# 模块: chat-direct-weather(天气直查接入:对话路径 + Agent 工具)

状态: draft r1 | 日期: 2026-09-08 | 触发: R-001/FR-3,4 | 对基线 chat-injection.md 的增量

## 对外接口
1) `ChatService.build_context(...)`:签名与返回结构**不变**(返回
   `{system_prompt, history, memory_context, analysis_result, sources}`);
   内部在 search_enabled 段、行情直查之后新增天气直查分支(时序见 design-change 数据流)。
2) Agent 注册表新增工具(LLM 可见 Schema):
```python
@tool(name="get_weather",
      description="查询指定城市的实时天气…",
      parameters={"type":"object","properties":{"city":{"type":"string"}},
                  "required":["city"]})
def get_weather(city: str): ...   # 调 core.weather.get_weather_context(f"{city}天气")
                                  # 未取到 → raise ValueError → 框架包装为失败 ToolResult
```
3) `sources` 新增条目类型 `{"source":"wttr-in","title":"wttr.in（实时天气）"}`,排在首位。

## 能力说明
- 提供: 天气问题命中时以实时数据替代 DDG 摘要注入 system_prompt;Agent 可 function-call 天气。
- 不提供: 多轮城市追问(依赖 LLM 自身行为);前端专属天气卡片。

## 内部关键逻辑
- 分支顺序: 行情直查 → 天气直查 → (天气命中则 decision={"tool":None} 跳过路由/DDG);
  天气未命中(非天气/取数失败)完全落回既有的路由→DDG 路径(基线行为零变化)。
- system_prompt 追加文案: "{天气上下文}\n请直接引用上述实时天气数据回答。"
- get_weather 复用城市识别:拼 `{city}天气` 让 is_weather_query 必真,城市名走 _to_cities
  映射;因此 get_weather 失败语义同 weather-core。
- user_id: get_weather 签名不含 user_id(无用户态),框架侧注入条件依赖 R-002 修复。

## 依赖
| 模块 | 使用的接口名 | 其文档 |
|---|---|---|
| weather-core | is_weather_query, get_weather_context | R-001/modules/weather-core.md |
| core/agent/tools | tool 注册表, execute_tool | 基线(预流程 S8)+ R-002 |
| chat_router | route | 基线不变 |
