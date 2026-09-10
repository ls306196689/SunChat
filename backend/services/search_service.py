"""
SunChat Backend - Search Service Wrapper
"""
from typing import List, Dict
from core.search import search_service
from core.llm import ollama_service
from utils.logger import logger

_UNSET = object()  # R-006: 区分"未传"与"传了 None(已试且失败)"


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

    def search_with_introduction(self, query: str, memories: List[Dict] = None,
                                  max_results: int = 5,
                                  stock_context=_UNSET) -> Dict:
        """
        搜索并使用 LLM 归纳答案

        Args:
            query: 搜索查询
            memories: 用户记忆（用于上下文增强）
            max_results: 最大结果数
            stock_context: R-006: 调用方已取的行情上下文(str 或 None=已试失败);
                           缺省时自取,行为与旧版完全一致。显式传入不再重复请求行情 API。

        Returns:
            包含 answer 和 sources 的结构化响应
        """
        # 股价类问题：DDG 摘要拿不到实时价格，先直查行情 API 把具体数字喂给 LLM
        if stock_context is _UNSET:
            try:
                from core.stock import get_stock_context
                stock_context = get_stock_context(query)
            except Exception as e:
                logger.debug(f"[SEARCH] 行情直查跳过: {e}")
                stock_context = None

        # 路由查询并获取意图
        route_result = self.route_query(query, memories)
        intent = route_result.get("intent", "general")
        enhanced_query = route_result.get("query", query)

        # 执行搜索
        search_results = self.search(enhanced_query, intent=intent, max_results=max_results)

        if not search_results and not stock_context:
            return {
                "answer": "未找到相关搜索结果。",
                "sources": [],
                "intent": intent
            }

        # 使用 LLM 归纳答案（行情数据置顶：这是权威数字，优先于搜索摘要）
        context = ((stock_context + "\n\n") if stock_context else "") + \
            self._build_context_from_results(search_results)
        answer = self._generate_answer(query, context, memories)

        sources = []
        if stock_context:
            sources.append({
                "title": "腾讯行情（实时数据）", "url": "https://gu.qq.com/",
                "source": "tencent-quote", "snippet": stock_context, "score": 1.0,
            })
        sources += [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "source": r.get("source", "duckduckgo"),
                "snippet": r.get("snippet", ""),
                "score": 0.8  # 简化评分
            }
            for r in search_results[:5]
        ]

        return {
            "answer": answer,
            "sources": sources,
            "intent": intent,
        }

    def _build_context_from_results(self, results: List[Dict]) -> str:
        """从搜索结果构建上下文"""
        context_parts = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "")
            url = result.get("url", "")
            snippet = result.get("snippet", result.get("body", ""))
            context_parts.append(f"[{i}] 标题: {title}\n链接: {url}\n摘要: {snippet}")
        return "\n\n".join(context_parts)

    def _generate_answer(self, query: str, context: str, memories: List[Dict] = None) -> str:
        """使用 LLM 归纳答案"""
        prompt = f"""基于以下搜索结果，回答用户的问题。

用户问题：{query}

搜索结果：
{context}

请回答用户的问题，如果搜索结果不相关，请说明。如果结果中提到了用户记忆中的内容，请引用它。

要求：
1. 使用中文回答
2. 保持回答简洁明了
3. 引用来源信息
4. 如果有多个相关来源，请综合回答
"""

        if memories:
            memory_text = "\n".join([f"- {m['content']}" for m in memories[:2]])
            prompt += f"\n\n用户背景信息：\n{memory_text}"

        prompt += "\n\n回答："

        try:
            answer = ollama_service.generate(prompt)
            return answer.strip()
        except Exception as e:
            logger.warning(f"[SEARCH] LLM 归纳失败，回退到摘要: {e}")
            # 回退到使用第一个结果的摘要
            return f"根据搜索结果，关于'{query}'的信息如下：\n\n{context[:500]}..."


# 全局实例
search_svc = SearchService()
