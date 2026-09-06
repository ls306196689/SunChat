"""
SunChat Backend - Chat Router
根据用户意图和上下文路由到不同的工具/服务
"""
import json
from typing import List, Dict, Optional
from datetime import datetime


class ChatRouter:
    """聊天路由器 - 决定如何处理用户请求"""

    def __init__(self):
        # 工具定义
        self.tools = [
            {
                "name": "memory",
                "description": "使用语义检索查询用户记忆/偏好",
                "when_to_use": "当用户询问关于自己历史、偏好、习惯等问题时"
            },
            {
                "name": "knowledge",
                "description": "从上传的文档中检索信息",
                "when_to_use": "当用户询问关于上传的文档内容时"
            },
            {
                "name": "search",
                "description": "进行网络搜索获取最新信息",
                "when_to_use": "当用户询问新闻、时事、最新信息时"
            },
            {
                "name": "chat",
                "description": "进行通用对话",
                "when_to_use": "当用户进行闲聊或没有明确目标时"
            }
        ]

        # 工具路由规则
        self.rules = {
            "memory": [
                r"我.*喜欢.*",
                r"我.*习惯.*",
                r"我.*最近.*",
                r"我.*之前.*",
                r"我的.*偏好",
                r"我的.*历史",
                r"记住.*",
                r"你记得.*"
            ],
            "knowledge": [
                r"文档.*",
                r"文件.*",
                r"上传.*",
                r"KB.*",
                r"知识库.*"
            ],
            "search": [
                r"最新.*",
                r"今天.*",
                r"新闻.*",
                r"搜索.*",
                r"谷歌.*",
                r"百度.*",
                r"什么是.*最新",
                r"股价|行情|涨了|跌了|收盘价|开盘价"
            ]
        }

    def route(self, query: str, context: Dict = None) -> Dict:
        """
        路由查询到合适的工具

        Args:
            query: 用户查询
            context: 上下文信息（包括记忆）

        Returns:
            路由结果，包含:
            - tool: 选择的工具名称
            - confidence: 置信度 (0-1)
            - intent: 意图分类
            - suggested_action: 建议的操作
        """
        intent = self._classify_intent(query)
        memories = context.get("memories", []) if context else []

        # 根据规则和意图决定工具
        tool, confidence = self._select_tool(query, intent, memories)

        return {
            "tool": tool,
            "confidence": confidence,
            "intent": intent,
            "memories": memories,
            "query": query,
            "suggested_action": self._get_suggested_action(tool, query, memories)
        }

    def _classify_intent(self, query: str) -> str:
        """分类用户意图"""
        query_lower = query.lower()

        # 检查是否询问记忆相关
        memory_patterns = [
            "我", "我的", "自己", "偏好", "习惯", "历史", "之前"
        ]
        if any(p in query_lower for p in memory_patterns):
            return "personal"

        # 检查是否询问文档相关
        knowledge_patterns = ["文档", "文件", "上传", "知识库", "KB"]
        if any(p in query_lower for p in knowledge_patterns):
            return "knowledge"

        # 检查是否询问最新信息
        search_patterns = ["最新", "今天", "新闻", "搜索", "谷歌", "百度"]
        if any(p in query_lower for p in search_patterns):
            return "search"

        return "general"

    def _select_tool(self, query: str, intent: str, memories: List[Dict]) -> tuple:
        """选择合适的工具"""
        query_lower = query.lower()

        # 检查是否有明确的工具匹配
        for tool_name, patterns in self.rules.items():
            for pattern in patterns:
                if __import__('re').search(pattern, query_lower):
                    return tool_name, 0.9

        # 根据意图选择
        if intent == "personal":
            return "memory", 0.8
        elif intent == "knowledge":
            return "knowledge", 0.85
        elif intent == "search":
            return "search", 0.8
        else:
            return "chat", 0.7

    def _get_suggested_action(self, tool: str, query: str, memories: List[Dict]) -> Dict:
        """获取建议的操作"""
        if tool == "memory":
            return {
                "action": "search_memories",
                "parameters": {
                    "query": query,
                    "top_k": 3,
                    "context": memories
                }
            }
        elif tool == "knowledge":
            return {
                "action": "search_knowledge",
                "parameters": {
                    "query": query
                }
            }
        elif tool == "search":
            return {
                "action": "web_search",
                "parameters": {
                    "query": query,
                    "memories": memories
                }
            }
        else:
            return {
                "action": "chat",
                "parameters": {
                    "query": query,
                    "memories": memories
                }
            }

    def get_tools(self) -> List[Dict]:
        """获取所有可用工具"""
        return self.tools


# 全局实例
chat_router = ChatRouter()
