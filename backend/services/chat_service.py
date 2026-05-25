"""
SunChat Backend - Chat Service
"""
import uuid
from typing import List, Dict, AsyncGenerator
from datetime import datetime

from app.config import settings
from core.llm import ollama_service
from core.embedding import embedding_service
from core.search import search_service
from models.sql_models import get_db, ChatSession, Message
from models.schemas import MessageCreate, MemoryResponse


class ChatService:
    """聊天服务"""

    def __init__(self):
        self.db = next(get_db())

    def create_session(self, user_id: int, title: str = None) -> Dict:
        """创建会话"""
        session = ChatSession(
            user_id=user_id,
            title=title or "新会话"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return {
            "session_id": str(session.id),
            "title": session.title,
            "created_at": session.created_at.isoformat()
        }

    def get_messages(self, session_id: int, page: int = 1, page_size: int = 20) -> Dict:
        """获取会话消息"""
        offset = (page - 1) * page_size
        messages = self.db.query(Message).filter(
            Message.session_id == session_id
        ).order_by(Message.created_at).offset(offset).limit(page_size).all()

        return {
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in messages
            ],
            "total": self.db.query(Message).filter(Message.session_id == session_id).count(),
            "page": page,
            "page_size": page_size
        }

    def generate_memory_from_message(self, user_message: str, ai_response: str) -> List[Dict]:
        """
        从对话中提取记忆

        使用 LLM 提取关键信息
        """
        prompt = f"""你是一个记忆提取器。请从以下对话中提取有用的记忆信息。

用户消息: {user_message}
AI 回答: {ai_response}

请以 JSON 格式输出提取的记忆，格式如下：
{{
    "memories": [
        {{
            "content": "提取的记忆内容",
            "type": "semantic/episodic",
            "category": "preference/skill/event",
            "importance": 5-10
        }}
    ]
}}

要求：
1. 只提取明确的事实信息
2. 临时性对话不提取
3. 重要性评分要准确
4. 如果没有有效记忆，返回空数组
请直接输出 JSON，不要有任何额外文本。
"""

        try:
            response = ollama_service.generate(prompt)
            # 尝试解析 JSON 响应
            import json
            # 清理响应，移除可能的 Markdown 代码块标记
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            result = json.loads(clean_response)
            return result.get("memories", [])
        except Exception as e:
            print(f"Memory extraction error: {e}, response: {response[:200]}")
            return []

    def build_memory_context(self, user_id: int, query: str, top_k: int = 5) -> List[Dict]:
        """构建记忆上下文（简化版：返回最近记忆）"""
        # 简化实现：实际应使用向量检索
        return [
            {"id": "mem_001", "content": "用户是程序员", "type": "semantic"},
            {"id": "mem_002", "content": "用户最近在学习 React", "type": "episodic"}
        ]

    def build_search_context(self, query: str, memories: List[Dict]) -> Dict:
        """构建搜索上下文"""
        return search_service.route_query(query, {"memories": memories})

    def generate(self, prompt: str, system: str = "") -> str:
        """使用 LLM 生成文本"""
        return ollama_service.generate(prompt, system)

    def process_stream_response(self, full_response: str, memories: List[Dict]) -> Dict:
        """处理响应（添加记忆更新信息）"""
        return {
            "response": full_response,
            "memory_updates": memories,
            "tokens_used": len(full_response) // 4  # 粗略估计
        }


# 全局实例
chat_service = ChatService()
