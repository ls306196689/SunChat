# 需求
设计一个Agent 来封装与大模型的交互和本地工具的调用，实现完整的对话流程和智能记忆管理。

# 核心框架

## 1. 核心架构：ReAct 循环模式
框架的灵魂应采用经典的 ReAct（Reasoning + Acting，推理与行动） 模式。传统的 AI 是一问一答，而 ReAct 模式通过”思考-行动-观察”的循环来解决复杂任务：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   感知      │────▶│   思考规划   │────▶│   行动执行   │
│Observation  │     │Thought/Intent │     │Action/Exec  │
└─────────────┘     └─────────────┘     └─────────────┘
        ▲                                     │
        └─────────────────────────────────────┘
```

- **感知 (Observation)**：接收用户指令、历史对话或工具返回的结果
- **思考与规划 (Thought/Intent)**：大模型分析当前状态，决定下一步做什么
- **行动 (Action/Tool Call)**：如果需要，大模型生成调用工具的指令
- **执行 (Execution)**：Python 逻辑解析指令，运行函数获取结果，并将结果反馈给大模型

## 2. 模块设计：极简的”瑞士军刀”架构
借鉴 MiniAgent 等优秀开源项目，框架的目录结构应刻意避免过度工程化，保持职责单一：

```
core/agent/
├── schema.py       # 数据基石：定义所有交互中使用的基本数据类型
├── tools.py        # 身手脚：提供 Agent 可以调用的具体能力
├── llm.py          # 输入输出：与大语言模型通信的接口
└── agent.py        # 大脑皮层：代理核心逻辑，实现 ReAct 循环
```

- **schema.py (数据基石)**：
  - `Message`：消息对象（role, content, timestamp）
  - `ToolResult`：工具执行结果（success, data, error）
  - `AgentState`：Agent 状态（current_step, thoughts, pending_actions）
  - `MemoryContext`：记忆上下文（short_term, long_term）

- **tools.py (手脚)**：
  - 提供 Agent 可以调用的具体能力
  - 支持装饰器模式和基类继承模式

- **llm.py (输入输出)**：
  - 与大语言模型通信的接口
  - 负责格式化请求和解析响应

- **agent.py (大脑皮层)**：
  - 代理核心逻辑，实现 ReAct 循环
  - 指挥其他组件协同工作

## 3. 工具系统：零样板代码与 Pythonic 设计
工具是 Agent 能力的延伸，自定义框架应追求定义工具的”零样板代码”。建议提供两种极简的赋能方式：

### 3.1 装饰器模式（推荐）
使用 @tool 装饰器，自动提取函数的 `__doc__` 或参数注解来生成给 LLM 看的工具描述，减少手动维护。

```python
@tool
def get_weather(city: str) -> str:
    “””获取指定城市的天气信息。
    
    Args:
        city: 城市名称
        
    Returns:
        天气信息字符串
    “””
    # 实现代码
    pass
```

**优点**：
- 利用 Python 的类型提示（如 `city: str`）帮助 LLM 理解参数格式
- 自动提取函数文档作为工具描述
- 定义即可用，无需额外配置

### 3.2 基类继承模式
对于复杂工具，提供 Tool 基类。基类的 run 方法应包含标准的异常捕获和返回格式。

```python
class SearchTool(Tool):
    name = “search”
    description = “搜索网络获取最新信息”
    
    def run(self, query: str) -> ToolResult:
        try:
            results = search_service(query)
            return ToolResult(success=True, data=results)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

**特点**：
- 标准的异常捕获和返回格式
- 即使工具执行失败，Agent 也能得到结构化的错误信息

## 4. 提示词工程驱动架构 (Prompt-Driven)
借鉴 openclaw-mini 的聪明设计，将复杂的逻辑控制留给 Markdown 提示词，而不是在 Python 代码里写大量 if-else 逻辑。

### 4.1 System Prompt 设计
通过精心设计的 System Prompt 教导 LLM 遵循严格的输出格式：

```
你是一个智能 Agent，需要使用 ReAct 模式解决用户问题。

你的输出必须遵循以下格式（始终使用 JSON）：
{
    “thought”: “你的思考过程，分析当前状态和下一步计划”,
    “action”: {
        “name”: “工具名称”,
        “parameters”: {
            “参数名”: “参数值”
        }
    },
    “observation”: “工具执行结果（如果是观察步骤）”
}

规则：
1. 每次思考后必须有一个行动，除非任务已完成
2. 行动必须是预定义的工具之一
3. 观察步骤用于返回工具执行结果
4. 任务完成后输出 “action”: {“name”: “finish”, “result”: “...”}
```

### 4.2 代码实现
Python 代码只负责 I/O 和流程控制，使用正则表达式（Regex）提取大模型输出中的 JSON 指令并执行。

```python
def parse_agent_output(text: str) -> Dict:
    “””解析 Agent 输出，提取 JSON 指令”””
    pattern = r'\{.*\}'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {“thought”: text, “action”: None}
```

## 5. 记忆系统：分层与可插拔
记忆是 Agent 的”经验”，框架的记忆系统应设计为分层和可插拔的。

### 5.1 短期记忆（短期对话历史）
- 使用简单的 Python 列表（`List[Dict]`）存储当前会话的对话历史
- 为防止超出上下文限制，实现”滑动窗口”或基于 Token 数的修剪策略

```python
class ShortTermMemory:
    def __init__(self, max_messages: int = 10, max_tokens: int = 4000):
        self.messages: List[Dict] = []
        self.max_messages = max_messages
        self.max_tokens = max_tokens
    
    def add(self, role: str, content: str):
        self.messages.append({“role”: role, “content”: content})
        self._trim()
    
    def _trim(self):
        “””滑动窗口修剪：移除最早的对话”””
        while len(self.messages) > self.max_messages:
            self.messages.pop(0)
```

### 5.2 长期记忆（向量数据库存储）
- 定义一个 `MemoryBackend` 抽象接口（包含 `store`, `retrieve`, `search` 方法）
- 框架内置一个基于内存字典的简单后端
- 允许用户无缝替换为向量数据库（如 Chroma）等外部存储

```python
from abc import ABC, abstractmethod
from typing import List, Dict

class MemoryBackend(ABC):
    @abstractmethod
    def store(self, content: str, metadata: Dict = None):
        “””存储记忆”””
        pass
    
    @abstractmethod
    def retrieve(self, memory_id: str) -> Dict:
        “””检索特定记忆”””
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        “””搜索相关记忆”””
        pass
```

### 5.3 记忆生命周期管理
- **创建**：从对话中自动提取有价值的记忆
- **检索**：根据用户输入和上下文检索相关记忆
- **更新**：当新记忆与旧记忆冲突时，以最新记忆为准
- **删除**：支持手动删除过时记忆

## 6. 与现有系统的集成

### 6.1 集成点
Agent 框架应与现有的 SunChat 系统集成：

| 模块 | 功能 | 集成方式 |
|------|------|---------|
| chat_service | 聊天服务 | 作为基础对话能力 |
| memory_service | 记忆服务 | 作为长期记忆后端 |
| search_service | 搜索服务 | 作为搜索工具 |
| knowledge_service | 知识库服务 | 作为知识检索工具 |

### 6.2 工具映射
Agent 的工具应映射到现有的服务：

| Agent 工具 | 对应服务 | 功能 |
|-----------|---------|------|
| `chat` | chat_service | 通用对话 |
| `memory_search` | memory_service | 搜索记忆 |
| `memory_create` | memory_service | 创建记忆 |
| `search` | search_service | 网络搜索 |
| `knowledge_search` | knowledge_service | 知识库搜索 |

## 7. 执行流程

### 7.1 简单任务流程
```
用户输入 → LLM 直接响应
```

### 7.2 复杂任务流程（ReAct）
```
用户输入
  ↓
LLM 分析 →Thought
  ↓
需要工具? ──否──→ 直接响应
  ↓是
LLM 生成工具调用 → Action
  ↓
执行工具 → Observation
  ↓
LLM 结合结果继续分析
  ↓
... 循环直到完成
```

### 7.3 对话流程（特殊优化）
对于简单的对话任务，可以跳过 ReAct 循环，直接使用优化的对话流程：

```
1. 用户输入信息
2. 构建 prompt + 用户输入信息 给 llm, 看需要查询什么记忆
3. 按照 llm 提示查询本地记忆
4. 本地记忆查询内容 + 用户输入信息 + 记忆提取 prompt 给到 llm
5. llm 返回记忆提取内容 以及 对用户输入信息的回复
6. 本地服务更新记忆, 如果有冲突以最新记忆为准
```

## 8. 错误处理

### 8.1 工具执行失败
- 捕获异常并返回结构化的错误信息
- 将错误信息传递给 LLM，让其决定如何处理

```python
ToolResult(success=False, error=”工具执行失败: 连接超时”)
```

### 8.2 LLM 解析失败
- 多次尝试解析
- 如果失败，返回清晰的错误信息

### 8.3 超时处理
- 为工具执行设置超时时间
- 为 LLM 调用设置超时时间
- 超时后返回错误信息

## 9. 性能优化

### 9.1 上下文修剪
- 基于 Token 数的滑动窗口
- 移除低重要性的历史消息

### 9.2 工具缓存
- 缓存相同参数的工具调用结果
- 支持手动刷新缓存

### 9.3 流式响应
- 支持 LLM 流式输出
- 实时显示 Agent 的思考过程

## 10. 测试策略

### 10.1 单元测试
- 测试每个工具的执行
- 测试记忆系统的 CRUD 操作

### 10.2 集成测试
- 测试完整的 ReAct 循环
- 测试与 LLM 的交互

### 10.3 E2E 测试
- 测试完整的用户场景
- 验证记忆的创建和检索

# 实现状态

## 已完成模块

### 1. 核心架构 (core/agent/)
- ✅ `schema.py` - 数据类型定义（Message, ToolResult, AgentState, MemoryContext, AgentConfig, Action）
- ✅ `llm.py` - LLM 通信接口（支持工具调用）
- ✅ `tools.py` - 工具定义（装饰器模式 + 基类继承模式）
- ✅ `agent.py` - Agent 核心逻辑（ReAct 循环 + 简化对话流程）

### 2. 工具系统
- ✅ `@tool` 装饰器 - 零样板代码定义工具
- ✅ `Tool` 基类 - 支持自定义工具
- ✅ 内置工具：
  - `chat` - 通用对话
  - `memory_search` - 记忆搜索
  - `memory_create` - 记忆创建
  - `search` - 网络搜索
  - `knowledge_search` - 知识库搜索

### 3. 记忆系统
- ✅ 短期记忆 - 对话历史列表
- ✅ 长期记忆 - Chroma 向量数据库集成
- ✅ 记忆路由器 - LLM 驱动的记忆类型分析
- ✅ 记忆提取器 - 从对话中提取记忆

### 4. 提示词工程
- ✅ System Prompt 驱动
- ✅ JSON 格式输出（Thought -> Action -> Observation）
- ✅ 正则表达式解析 LLM 输出

### 5. 错误处理
- ✅ 工具执行异常捕获
- ✅ LLM 调用超时处理
- ✅ 结构化错误信息返回

## API 使用示例

```python
from core.agent import Agent, agent

# 创建 Agent 实例
agent_instance = Agent()

# 简化处理流程（优化的对话流程）
result = agent_instance.process_simple("你好，我叫孙鹏飞")
print(result["result"])  # AI 响应
print(result["memory_updates"])  # 提取的记忆

# 完整 ReAct 处理流程
result = agent_instance.process("帮我搜索一下今天的天气")
print(result["result"])
print(result["thoughts"])
print(result["tool_results"])
```

## 文件结构

```
backend/core/agent/
├── __init__.py       # 包导出
├── schema.py         # 数据类型定义
├── tools.py          # 工具定义
├── llm.py            # LLM 通信接口
└── agent.py          # Agent 核心逻辑
```