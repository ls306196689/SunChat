"""
SunChat Backend - Search Service Wrapper
"""
from typing import List, Dict
from core.search import search_service


class SearchService:
    """搜索服务（封装 core.search）"""

    def __init__(self):
        self.service = search_service

    def search(self, query: str, intent: str = None,
               max_results: int = 5) -> List[Dict]:
        """执行搜索"""
        if intent:
            # 特定意图搜索
            if intent == "news":
                query = f"最新 {query}"
            elif intent == "academic":
                query = f"论文 {query}"

        return self.service.search(query, max_results)

    def route_query(self, query: str, memories: List[Dict] = None) -> Dict:
        """智能路由"""
        context = {"memories": memories} if memories else None
        return self.service.route_query(query, context)


# 全局实例
search_svc = SearchService()
