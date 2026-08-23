"""
SunChat Backend - Agent Tools
提供 Agent 可以调用的具体能力
"""
import json
import re
from typing import List, Dict, Any, Optional, Callable
from functools import wraps
from dataclasses import dataclass

from core.memory_router import memory_router
from core.memory_extractor import memory_extractor
from services.memory_service import memory_service
from services.chat_service import chat_service
from core.search import search_service
from utils.logger import logger


# 工具注册表
_registered_tools: Dict[str, 'Tool'] = {}


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict = None

    def to_dict(self) -> Dict:
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class Tool:
    """工具基类"""

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    def __init__(self):
        self.name = getattr(self, 'name', self.__class__.__name__.lower())
        self.description = getattr(self, 'description', self.__doc__ or "")

    def run(self, **kwargs) -> ToolResult:
        """执行工具"""
        raise NotImplementedError

    def to_definition(self) -> Dict:
        """转换为工具定义"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


# 装饰器模式
def tool(name: str = None, description: str = None):
    """
    工具装饰器 - 零样板代码定义工具

    Args:
        name: 工具名称（默认为函数名）
        description: 工具描述（默认为函数 docstring）

    Returns:
        包装函数
    """
    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__
        func_description = description or func.__doc__ or ""

        # 提取参数信息
        import inspect
        sig = inspect.signature(func)
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            # 获取参数类型
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == str:
                    param_type = "string"
                elif param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"

            parameters["properties"][param_name] = {"type": param_type}

            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)

        # 创建工具定义
        tool_def = {
            "name": func_name,
            "description": func_description,
            "parameters": parameters,
            "function": func
        }

        # 存储工具定义
        func._tool_definition = tool_def

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return ToolResult(success=True, data=result)
            except Exception as e:
                logger.error(f"[TOOL] {func_name} 执行失败 - 错误:{e}")
                return ToolResult(success=False, error=str(e))

        # 注册工具
        _registered_tools[func_name] = tool_def

        return wrapper

    return decorator


# 预定义工具

class ChatTool(Tool):
    """通用对话工具"""

    name = "chat"
    description = "进行通用对话，回答用户问题"

    def run(self, message: str, memory_enabled: bool = True) -> ToolResult:
        """执行对话"""
        try:
            # 简单的对话，直接返回提示
            return ToolResult(
                success=True,
                data="这是一个通用对话工具，实际对话由主 Agent 处理。",
                metadata={"memory_enabled": memory_enabled}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MemorySearchTool(Tool):
    """记忆搜索工具"""

    name = "memory_search"
    description = "搜索用户的长期记忆，根据用户输入查询相关记忆"

    def run(self, query: str, top_k: int = 5, user_id: int = 1) -> ToolResult:
        """搜索记忆"""
        try:
            logger.info(f"[TOOL] memory_search - 查询:{query}, top_k:{top_k}")

            # 使用 MemoryRouter 分析查询
            analysis_result = memory_router.analyze_memory_need(query)

            # 查询记忆
            results = memory_service.search_memories_by_analysis(
                user_id=user_id,
                analysis_result=analysis_result,
                top_k=top_k
            )

            return ToolResult(
                success=True,
                data={
                    "memories": results,
                    "analysis": analysis_result
                },
                metadata={"query": query, "top_k": top_k}
            )
        except Exception as e:
            logger.error(f"[TOOL] memory_search 失败 - 错误:{e}")
            return ToolResult(success=False, error=str(e))


class MemoryCreateTool(Tool):
    """记忆创建工具"""

    name = "memory_create"
    description = "创建新记忆，当用户提供了重要信息时使用"

    def run(
        self,
        content: str,
        memory_type: str = "semantic",
        category: str = "general",
        importance: int = 5,
        user_id: int = 1
    ) -> ToolResult:
        """创建记忆"""
        try:
            logger.info(f"[TOOL] memory_create - 内容:{content[:50]}..., category:{category}")

            # 创建记忆
            result = memory_service.create_memory(
                user_id=user_id,
                content=content,
                memory_type=memory_type,
                category=category,
                importance=importance
            )

            return ToolResult(
                success=True,
                data=result,
                metadata={"content": content}
            )
        except Exception as e:
            logger.error(f"[TOOL] memory_create 失败 - 错误:{e}")
            return ToolResult(success=False, error=str(e))


class SearchTool(Tool):
    """网络搜索工具"""

    name = "search"
    description = "搜索网络获取最新信息"

    def run(self, query: str) -> ToolResult:
        """搜索网络"""
        try:
            logger.info(f"[TOOL] search - 查询:{query}")

            # 调用搜索服务
            result = search_service.route_query(query)

            return ToolResult(
                success=True,
                data=result,
                metadata={"query": query}
            )
        except Exception as e:
            logger.error(f"[TOOL] search 失败 - 错误:{e}")
            return ToolResult(success=False, error=str(e))


class KnowledgeSearchTool(Tool):
    """知识库搜索工具"""

    name = "knowledge_search"
    description = "从知识库中检索信息"

    def run(self, query: str) -> ToolResult:
        """搜索知识库"""
        try:
            logger.info(f"[TOOL] knowledge_search - 查询:{query}")

            # 调用知识库搜索
            from services.knowledge_service import knowledge_service
            results = knowledge_service.search(query)

            return ToolResult(
                success=True,
                data=results,
                metadata={"query": query}
            )
        except Exception as e:
            logger.error(f"[TOOL] knowledge_search 失败 - 错误:{e}")
            return ToolResult(success=False, error=str(e))


# 工具注册函数
def register_builtin_tools():
    """注册内置工具"""
    tools = [
        ChatTool(),
        MemorySearchTool(),
        MemoryCreateTool(),
        SearchTool(),
        KnowledgeSearchTool()
    ]

    for tool in tools:
        _registered_tools[tool.name] = {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "tool": tool
        }

    return _registered_tools


def get_tool(name: str) -> Optional[Tool]:
    """获取工具"""
    tool_def = _registered_tools.get(name)
    if tool_def and "tool" in tool_def:
        return tool_def["tool"]
    return None


def get_tool_definition(name: str) -> Optional[Dict]:
    """获取工具定义"""
    return _registered_tools.get(name)


def get_all_tools() -> List[Dict]:
    """获取所有工具定义"""
    return list(_registered_tools.values())


# 注册内置工具
register_builtin_tools()
