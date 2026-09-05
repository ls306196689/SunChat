# 06 · Agent 框架优化方案（打磨成正式功能）

## 1. 现状
- 模块：[core/agent/](../../backend/core/agent/) — `agent.py`(ReAct 循环)、`llm.py`(AgentLLM)、`tools.py`(5 工具)、`schema.py`(dataclass)。
- **目前是死代码**：无任何路由引用 `agent`。
- 问题：用"让 LLM 输出 JSON 文本再解析"的伪 ReAct，而非 Ollama 原生 tool_calls；内部有 bug。

## 2. 问题清单
| # | 问题 | 位置 | 严重度 |
|---|------|------|--------|
| A1 | 无路由接线，功能不可用 | — | 致命 |
| A2 | `agent_llm.build_messages` 对 `ToolResult` dataclass 调 `.get()`（应 `to_dict()`）→ AttributeError | agent/llm.py:159 | 高 |
| A3 | history 里 `role:"tool"` 无 tool_calls 配对，Ollama 会拒收 | agent/llm.py:156 | 高 |
| A4 | 伪 ReAct（JSON 文本解析）脆弱，小模型易输出非法 JSON | agent.py:97 | 高 |
| A5 | `ChatTool` 是 stub（返回固定提示语） | agent/tools.py:146 | 中 |
| A6 | 工具无 user_id 注入，`user_id=1` 默认 | agent/tools.py | 中 |
| A7 | `Agent` 全局单例，`conversation_history` 跨请求污染 | agent.py:460 | 中 |
| A8 | `ToolResult` 在 `schema.py` 和 `tools.py` 各定义一份（重名冲突隐患） | agent/ | 低 |

## 3. 优化设计

### 3.1 架构：Ollama 原生 tool_calls 的 Agent 循环
放弃"LLM 输出 JSON 文本"的伪 ReAct，改用 Ollama `/api/chat` 的 `tools` 参数（OpenAI 风格）。循环：
```
messages = [system(角色+可用能力说明), ...history, user]
for i in range(max_iterations):
    resp = ollama.chat(messages, tools=tool_schemas)
    msg = resp["message"]
    if msg.get("tool_calls"):
        for tc in msg["tool_calls"]:
            result = execute_tool(tc["function"]["name"], tc["function"]["arguments"])
            messages.append({"role":"assistant","content":msg.get("content",""),"tool_calls":msg["tool_calls"]})
            messages.append({"role":"tool","content":json.dumps(result),"name":tc["function"]["name"]})
        continue
    else:
        return msg["content"]   # 最终答案
return "达到最大迭代，返回已有结果"
```
- 关键点：`role:"tool"` 消息**必须**紧跟在带 `tool_calls` 的 assistant 消息之后，且带 `name`——这样 Ollama 才接受（修 A3）。
- 工具结果 `content` 用 `json.dumps(..., ensure_ascii=False)`（修 A2 的 dataclass.get）。

### 3.2 工具定义（schema.py → OpenAI 风格）
每个工具给出 `{type:"function", function:{name, description, parameters(JSON Schema)}}`。参数 JSON Schema 由现有 `parameters` 补齐 `type/properties/required`。
工具集（保留 4 个真实工具，删/改 ChatTool）：
- `memory_search(query, top_k)` → `memory_service.search_memories`
- `memory_create(content, type, category, importance)` → `memory_service.create_memory`
- `web_search(query)` → `search_service.search`
- `knowledge_search(query, file_ids?)` → `knowledge_service.search_knowledge`
- **A5**：删除 `ChatTool`（"通用对话"本身就是 Agent 的主职责，无需工具）。
- **A6**：工具执行时注入 `user_id`（从请求上下文，默认本地单用户 USER_ID）。

### 3.3 纯文本回退（应对模型不支持 tool_calls）
若 Ollama/模型返回无 `tools` 支持或 `tool_calls` 始终为空但用户明显需要工具：
- 第一轮若模型直接给答案 → 正常返回（无需工具的场景）。
- 加**能力探测**：`/chat/agent` 首次调用前，用一个简单 probe 判断当前模型是否支持 tool_calls；不支持则降级为"单轮增强"（把工具能力写进 system prompt，让模型直接给答案，不做循环）。
- `max_iterations`（默认 5）兜底防死循环。

### 3.4 会话隔离（A7）
- `Agent` 不再持全局 `conversation_history` 状态；改为**无状态**：每次 `/chat/agent` 请求传入 `messages`（或 session_id 从 DB 取历史），循环内的 `messages` 是局部变量。
- 可选：Agent 对话也落 `Message` 表（role=assistant，content 为最终答案），复用会话体系。

### 3.5 端点
```python
class AgentRequest(BaseModel):
    content: str
    session_id: Optional[str] = None
    max_iterations: int = 5
    user_id: int = USER_ID

@router.post("/chat/agent")
def agent_chat(req, db=Depends(get_db)):
    result = agent.run(req.content, history=..., user_id=req.user_id, max_iterations=req.max_iterations)
    # 落库 user + assistant 消息
    return {"code":200, "data":{"result":result["content"],"tool_calls":result["tool_trace"],"iterations":...}}
```
- 返回 `tool_trace`（调了哪些工具、入参、摘要结果）便于前端展示"Agent 做了什么"。

## 4. 涉及文件
- [agent/agent.py](../../backend/core/agent/agent.py)：重写 `run()` 为原生 tool_calls 循环，无状态化
- [agent/llm.py](../../backend/core/agent/llm.py)：`chat_with_tools`、修 `build_messages`（role:tool 配对）、复用统一 LLM 客户端
- [agent/tools.py](../../backend/core/agent/tools.py)：删 ChatTool、工具注入 user_id、JSON Schema
- [agent/schema.py](../../backend/core/agent/schema.py)：统一 `ToolResult`（去掉 tools.py 重名）
- [chat.py](../../backend/app/api/v1/routes/chat.py) 或新增 `agent.py` 路由：`/chat/agent`
- 新增 `core/sse.py` 无关；`tools` schema 构建 util

## 5. 验证
- 单测（mock LLM，**不依赖真实 tool_calls 模型**）：
  - `test_agent_calls_tool_then_answers`：mock 第 1 轮返回 tool_calls(memory_search)、第 2 轮返回 content → 断言工具被调、最终答案正确
  - `test_agent_multi_tool`：一轮多个 tool_calls 都执行
  - `test_agent_max_iterations`：mock 一直 tool_calls → 到 max 终止、不无限循环
  - `test_agent_no_tool_needed`：mock 直接 content → 1 轮返回
  - `test_tool_result_serialized`：tool 消息 content 为合法 JSON（修 A2/A3）
  - `test_agent_stateless`：两次请求互不污染 history
- 实机（Ollama 在线 + 支持 tool_calls 的模型，如 qwen2.5:7b 新版 Ollama）：
  - [ ] "我叫小明，记住我" → 触发 memory_create
  - [ ] "我上周买了什么" → 触发 memory_search 并整合答案
  - [ ] "今天有什么新闻" → 触发 web_search

## 6. 执行结果（执行后回填）
- [x] 原生 tool_calls 循环（Ollama /api/chat tools 参数；role:tool 紧跟带 tool_calls 的 assistant、带 name；ToolResult→json.dumps 序列化，修 A2/A3/A4）
- [x] 纯文本回退（不支持 tools 的模型：异常后无 tools 重试 / 不产 tool_calls 直接返回文本；max_iterations 兜底）
- [x] /chat/agent 端点（sanitize + 会话落库 + tool_trace 返回），已注册 main.py
- [x] 无状态化（每次 run 局部 messages，修 A7）；删 ChatTool（A5）；ToolResult 单一来源 schema.py（A8）；user_id 强制注入且 LLM 覆盖无效（A6）
- 测试结果：tests/test_agent.py 11 通过（工具→答案、多工具、max 迭代、直答、配对合法性、JSON 字符串参数、无状态隔离、越权免疫、文本回退、端点两条）。实机：qwen2.5:7b/新版 Ollama 上"记住我叫X/查我上周/今天新闻"三条路径待验。
