"""
SunChat Backend - Agent Tools
提供 Agent 可调用的工具：OpenAI/Ollama 原生 function-calling Schema + 真实执行。

约定：
- user_id 由 Agent 循环注入，不作为 LLM 可见参数（防越权，修 A6）
- 工具返回 schema.ToolResult（单一来源，修 A8 重名问题）
"""
import json
from typing import List, Dict, Any, Optional, Callable
from functools import wraps

from core.agent.schema import ToolResult, ToolDefinition
from services.memory_service import memory_service
from core.search import search_service
from app.config import settings
from utils.logger import logger


# 工具注册表：name -> ToolDefinition
_registered: Dict[str, ToolDefinition] = {}


def tool(name: str, description: str, parameters: Dict[str, Any]):
    """注册工具装饰器：parameters 为 JSON Schema（type/properties/required）。

    被装饰函数须返回可 JSON 序列化对象；异常自动包装为失败 ToolResult。
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def runner(**kwargs):
            try:
                data = func(**kwargs)
                return ToolResult(success=True, data=data)
            except Exception as e:
                logger.error(f"[TOOL] {name} 执行失败 - 错误:{e}")
                return ToolResult(success=False, error=str(e))

        _registered[name] = ToolDefinition(
            name=name, description=description,
            parameters=parameters, function=runner)
        return runner
    return decorator


def _clean(kwargs: Dict[str, Any], allowed: List[str]) -> Dict[str, Any]:
    """只保留 Schema 声明的参数，防止 LLM 注入多余字段。"""
    return {k: v for k, v in kwargs.items() if k in allowed}


# ==================== 工具实现 ====================

@tool(
    name="memory_search",
    description="搜索用户的长期记忆/偏好/经历。当回答需要用户的个人信息时使用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词或自然语言查询"},
            "top_k": {"type": "integer", "description": "返回条数，默认 5"},
        },
        "required": ["query"],
    },
)
def memory_search(query: str, top_k: int = 5, user_id: int = None):
    return memory_service.search_memories(
        user_id=user_id or settings.LOCAL_USER_ID, query=query,
        top_k=int(top_k) if top_k else 5)


@tool(
    name="memory_create",
    description="为用户创建一条新记忆（用户告知的名字/偏好/事实/事件时使用）。",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "完整明确的记忆陈述，如：用户叫小明"},
            "category": {"type": "string",
                         "description": "preference/person/event/knowledge/relationship/habit/general"},
            "importance": {"type": "integer", "description": "1-10，名字等关键信息为 10"},
        },
        "required": ["content"],
    },
)
def memory_create(content: str, category: str = "general",
                  importance: int = 5, user_id: int = None):
    return memory_service.create_memory(
        user_id=user_id or settings.LOCAL_USER_ID, content=content,
        memory_type="semantic", category=category or "general",
        importance=int(importance) if importance else 5)


@tool(
    name="web_search",
    description="联网搜索获取实时/最新信息（新闻、行情、时效性内容）。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "max_results": {"type": "integer", "description": "结果条数，默认 5"},
        },
        "required": ["query"],
    },
)
def web_search(query: str, max_results: int = 5):
    return search_service.search(query, max_results=int(max_results) or 5)


@tool(
    name="knowledge_search",
    description="从用户上传的知识库文档中检索相关内容。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索问题"},
            "top_k": {"type": "integer", "description": "返回条数，默认 5"},
        },
        "required": ["query"],
    },
)
def knowledge_search(query: str, top_k: int = 5, user_id: int = None):
    from services.knowledge_service import knowledge_service
    return knowledge_service.search_knowledge(
        user_id=user_id or settings.LOCAL_USER_ID, query=query,
        top_k=int(top_k) if top_k else 5)


# ==================== 注册表访问 ====================

def get_tool(name: str) -> Optional[ToolDefinition]:
    return _registered.get(name)


def get_all_tool_definitions() -> List[ToolDefinition]:
    return list(_registered.values())


def get_openai_tool_schemas() -> List[Dict]:
    """OpenAI/Ollama 原生 tools 参数格式。"""
    return [td.to_openai_format() for td in _registered.values()]


def execute_tool(name: str, arguments: Dict[str, Any],
                 user_id: int = None) -> ToolResult:
    """按名称执行工具；user_id 强制注入且 LLM 无法覆盖。"""
    td = _registered.get(name)
    if not td:
        return ToolResult(success=False, error=f"未知工具: {name}")

    args = dict(arguments or {})
    args.pop("user_id", None)  # 防 LLM 伪造 user_id
    args["user_id"] = user_id or settings.LOCAL_USER_ID

    allowed = set((td.parameters or {}).get("properties", {}).keys()) | {"user_id"}
    args = {k: v for k, v in args.items() if k in allowed}

    # 类型宽松转换：Ollama 部分版本把数字传成字符串
    props = (td.parameters or {}).get("properties", {})
    for key, spec in props.items():
        if key in args and spec.get("type") == "integer":
            try:
                args[key] = int(args[key])
            except (TypeError, ValueError):
                pass

    return td.function(**args)
