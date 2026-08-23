"""
SunChat Backend - Agent Schema
定义所有交互中使用的基本数据类型
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    """消息对象"""
    role: str  # user, assistant, system, tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name
        }

    @staticmethod
    def from_dict(data: Dict) -> "Message":
        return Message(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            tool_call_id=data.get("tool_call_id"),
            tool_name=data.get("tool_name")
        )


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        result = {
            "success": self.success
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @staticmethod
    def success_result(data: Any, metadata: Dict = None) -> "ToolResult":
        return ToolResult(success=True, data=data, metadata=metadata or {})

    @staticmethod
    def error_result(error: str, metadata: Dict = None) -> "ToolResult":
        return ToolResult(success=False, error=error, metadata=metadata or {})


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Any = None

    def to_openai_format(self) -> Dict:
        """转换为 OpenAI 格式的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


@dataclass
class AgentState:
    """Agent 状态"""
    current_step: str = "init"  # init, think, act, observe, complete
    thoughts: List[str] = field(default_factory=list)
    pending_actions: List[Dict] = field(default_factory=list)
    current_action: Optional[Dict] = None
    observation: Optional[str] = None
    final_result: Optional[str] = None
    tool_results: List[ToolResult] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "current_step": self.current_step,
            "thoughts": self.thoughts,
            "pending_actions": self.pending_actions,
            "current_action": self.current_action,
            "observation": self.observation,
            "final_result": self.final_result,
            "tool_results": [r.to_dict() for r in self.tool_results]
        }


@dataclass
class MemoryContext:
    """记忆上下文"""
    short_term: List[Dict] = field(default_factory=list)
    long_term: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "short_term": self.short_term,
            "long_term": self.long_term
        }


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_iterations: int = 10
    max_tokens: int = 4000
    temperature: float = 0.7
    system_prompt: str = ""
    tools: List[ToolDefinition] = field(default_factory=list)

    @staticmethod
    def default() -> "AgentConfig":
        return AgentConfig(
            max_iterations=10,
            max_tokens=4000,
            temperature=0.7,
            system_prompt="你是一个智能 Agent，需要使用 ReAct 模式解决用户问题。"
        )


@dataclass
class Action:
    """动作"""
    name: str
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "parameters": self.parameters
        }
