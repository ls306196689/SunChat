"""
SunChat Backend - Search Service
"""
import re
from typing import List, Dict
from duckduckgo_search import DDGS


class SearchService:
    """搜索服务（使用 DuckDuckGo）"""

    def __init__(self):
        self.ddgs = DDGS()

    def search(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """
        执行搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        try:
            results = self.ddgs.text(query, max_results=max_results)
            return list(results)
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def route_query(self, query: str, context: Dict = None) -> str:
        """
        智能路由搜索查询

        Args:
            query: 原始查询
            context: 用户上下文

        Returns:
            路由后的查询类型和优化后的查询
        """
        # 意图分类
        if re.search(r"最新|今天|刚刚|news", query, re.IGNORECASE):
            intent = "news"
        elif re.search(r"论文|研究|学术|paper", query, re.IGNORECASE):
            intent = "academic"
        elif re.search(r"价格|购买|评测", query, re.IGNORECASE):
            intent = "commerce"
        elif re.search(r"代码|bug|API|github", query, re.IGNORECASE):
            intent = "code"
        else:
            intent = "general"

        # 如果有上下文，增强查询
        if context and context.get("memories"):
            memory_text = " ".join([m["content"] for m in context["memories"][:3]])
            enhanced_query = f"{query} (用户背景: {memory_text})"
        else:
            enhanced_query = query

        return {
            "intent": intent,
            "query": enhanced_query
        }

    def check_availability(self) -> bool:
        """检查搜索服务是否可用"""
        try:
            result = self.ddgs.text("test", max_results=1)
            return len(result) > 0
        except Exception:
            return False


search_service = SearchService()
