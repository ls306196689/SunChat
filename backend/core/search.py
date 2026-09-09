"""
SunChat Backend - Search Service
优先使用 ddgs（duckduckgo_search 后继维护包），旧包作回退；带超时。
"""
import re
import time
from typing import List, Dict, Optional

from app.config import settings
from utils.logger import logger

try:
    from ddgs import DDGS
except ImportError:  # 旧包回退
    from duckduckgo_search import DDGS


class SearchService:
    """搜索服务（使用 DuckDuckGo）"""

    AVAIL_TTL = 60  # 探活缓存秒数

    def __init__(self):
        self._avail_cache = None  # (monotonic_ts, bool)
        # 不同版本 DDGS 对 timeout 参数支持不一，做兼容
        try:
            self.ddgs = DDGS(timeout=settings.SEARCH_TIMEOUT)
        except TypeError:
            self.ddgs = DDGS()

    def search(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """执行搜索（失败返回空列表，不抛异常）。结果字段归一化：href -> url。"""
        try:
            results = self.ddgs.text(query, max_results=max_results)
            normalized = []
            for r in results or []:
                item = dict(r)
                if not item.get("url") and item.get("href"):
                    item["url"] = item["href"]
                if not item.get("snippet") and item.get("body"):
                    item["snippet"] = item["body"]
                normalized.append(item)
            return normalized
        except Exception as e:
            logger.warning(f"[SEARCH] 搜索失败: {e}")
            return []

    def route_query(self, query: str, context: Dict = None) -> Dict:
        """
        智能路由搜索查询（正则意图分类）。

        注意：记忆不拼进搜索词（避免污染），仅作为 LLM 归纳时的背景，
        由 search_with_introduction 处理。
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

        return {
            "intent": intent,
            "query": query
        }

    def check_availability(self) -> bool:
        """检查搜索服务是否可用（结果缓存 60s，健康检查轮询不再每次打 DDG）。"""
        now = time.monotonic()
        if self._avail_cache is not None:
            ts, val = self._avail_cache
            if now - ts < self.AVAIL_TTL:
                return val
        try:
            result = self.ddgs.text("test", max_results=1)
            val = len(result) > 0
        except Exception:
            val = False
        self._avail_cache = (now, val)
        return val


search_service = SearchService()
