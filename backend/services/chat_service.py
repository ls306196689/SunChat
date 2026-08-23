"""
SunChat Backend - Chat Service with Logging
"""
import uuid
import json
import re
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

from app.config import settings
from core.llm import ollama_service
from core.embedding import embedding_service
from core.search import search_service
from core.memory_router import memory_router
from core.memory_extractor import memory_extractor
from services.memory_service import memory_service
from models.sql_models import get_db, ChatSession, Message
from models.schemas import MessageCreate, MemoryResponse
from utils.logger import chat_logger, memory_logger, logger


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

        使用 LLM 提取关键信息（保留作为回退方案）
        """
        prompt = f"""你是一个智能记忆提取器。请从以下对话中提取对用户有价值的记忆信息。

用户消息: {user_message}
AI 回答: {ai_response}

请以 JSON 格式输出提取的记忆，格式如下：
{{
    "memories": [
        {{
            "content": "提取的记忆内容（完整、明确的陈述）",
            "type": "semantic/episodic",
            "category": "preference/skill/event/work/name/hobby",
            "importance": 1-10
        }}
    ]
}}

要求：
1. **优先从用户消息中提取明确的事实信息**
2. 用户主动告诉你的信息（如名字、偏好、背景）是重要的记忆
3. 用户描述的事实、观点、经历都应提取
4. 即使是简单的陈述，只要包含有用信息就提取
5. 如果用户提供了名字，必须以"用户叫[名字]"格式存储，重要性必须是 10
6. 对于用户提问，如果提问本身透露了信息（如"我叫什么"暗示用户想提供名字），也应提取
7. 即使没有明确的个人相关信息，如果对话中有任何有用的信息，也应提取
8. 如果确实没有任何有效信息，返回空数组 []
请直接输出 JSON，不要有任何额外文本。
"""

        try:
            logger.debug(f"[CHAT] 开始记忆提取 - 用户消息长度:{len(user_message)}, AI响应长度:{len(ai_response)}")
            response = ollama_service.generate(prompt)
            logger.debug(f"[CHAT] LLM 原始响应: {response[:300]}")

            # 尝试解析 JSON 响应
            # 清理响应，移除可能的 Markdown 代码块标记
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            result = json.loads(clean_response)
            memories = result.get("memories", [])
            logger.info(f"[CHAT] 记忆提取完成 - 提取到 {len(memories)} 条记忆")
            for i, m in enumerate(memories):
                logger.debug(f"[CHAT]   提取的记忆{i+1}: {m.get('content', '')[:50]}..., 类型:{m.get('type')}, 类别:{m.get('category')}, 评分:{m.get('importance')}")
            return memories
        except json.JSONDecodeError as e:
            logger.error(f"[CHAT] JSON 解析失败 - 错误:{e}, 响应: {response[:300]}")
            return []
        except Exception as e:
            logger.error(f"[CHAT] 记忆提取失败 - 错误:{e}, 响应: {response[:300] if 'response' in dir() else 'N/A'}")
            return []

    def build_memory_context(self, user_id: int, query: str, top_k: int = 3) -> List[Dict]:
        """构建记忆上下文（使用 Chroma 向量检索）"""
        try:
            # 使用语义检索搜索相关记忆
            results = memory_service.search_memories(
                user_id=user_id,
                query=query,
                top_k=top_k
            )

            # 格式化为记忆上下文
            return [
                {
                    "id": r.get("memory_id", ""),
                    "content": r.get("content", ""),
                    "similarity": r.get("similarity", 0),
                    "type": r.get("metadata", {}).get("type", "semantic"),
                    "category": r.get("metadata", {}).get("category", "general")
                }
                for r in results if r.get("similarity", 0) > 0.3  # 过滤低相似度结果
            ]
        except Exception as e:
            logger.error(f"[CHAT] 构建记忆上下文失败 - 错误:{e}")
            return []

    def build_search_context(self, query: str, memories: List[Dict]) -> Dict:
        """构建搜索上下文"""
        return search_service.route_query(query, {"memories": memories} if memories else None)

    def generate(self, prompt: str, system: str = "", model: str = None) -> str:
        """使用 LLM 生成文本（model 可选，默认动态解析）"""
        return ollama_service.generate(prompt, system, model=model)

    def generate_stream(self, prompt: str, system: str = "", model: str = None) -> AsyncGenerator[str, None]:
        """使用 LLM 生成文本（流式）"""
        return ollama_service.generate(prompt, system, stream=True, model=model)

    def process_stream_response(self, full_response: str, memories: List[Dict]) -> Dict:
        """处理响应（添加记忆更新信息）"""
        return {
            "response": full_response,
            "memory_updates": memories,
            "tokens_used": len(full_response) // 4  # 粗略估计
        }

    def _build_extraction_prompt_for_llm(self, user_input: str, context_memories: List[Dict] = None) -> str:
        """
        构建记忆提取prompt

        Args:
            user_input: 用户输入
            context_memories: 上下文记忆

        Returns:
            提取prompt
        """
        context_text = ""
        if context_memories:
            context_text = "\n\n相关上下文记忆：\n"
            for i, mem in enumerate(context_memories[:5], 1):
                context_text += f"{i}. {mem.get('content', '')}\n"

        return f"""你是一个智能记忆提取器。请从以下对话中提取对用户有价值的记忆信息。

用户输入: {user_input}{context_text}

请以 JSON 格式输出提取的记忆，格式如下：
{{
    "memories": [
        {{
            "content": "提取的记忆内容（完整、明确的陈述）",
            "type": "semantic/episodic",
            "category": "preference/person/event/knowledge/relationship/habit/general",
            "importance": 1-10
        }}
    ]
}}

要求：
1. 优先从用户输入中提取明确的事实信息
2. 用户主动告诉你的信息（如名字、偏好、背景）是重要的记忆
3. 用户描述的事实、观点、经历都应提取
4. 即使是简单的陈述，只要包含有用信息就提取
5. 如果用户提供了名字，必须以"用户叫[名字]"格式存储，重要性必须是 10
6. 对于用户提问，如果提问本身透露了信息，也应提取
7. 即使没有明确的个人相关信息，如果对话中有任何有用的信息，也应提取
8. 如果确实没有任何有效信息，返回空数组 []
9. 请直接输出 JSON，不要有任何额外文本。
"""

    def _build_final_system_prompt(self, user_input: str, memory_context: List[Dict], analysis_result: Dict) -> str:
        """
        构建最终的系统prompt

        Args:
            user_input: 用户输入
            memory_context: 记忆上下文
            analysis_result: 记忆分析结果

        Returns:
            系统prompt
        """
        # 基础系统提示
        system_prompt = "你是一个智能助手。请回答用户问题。"

        # 添加记忆上下文
        if memory_context:
            memory_text = "\n".join([f"- {m['content']} (相似度: {m['similarity']:.2f})" for m in memory_context])
            system_prompt += f"\n\n用户背景信息（基于语义检索的记忆）：\n{memory_text}"

        # 添加记忆分析结果
        memory_types = analysis_result.get("recommended_memory_types", [])
        if memory_types:
            system_prompt += f"\n\n需要关注的记忆类型：{', '.join(memory_types)}"

        return system_prompt

    def process_message(self, user_id: int, session_id: int, content: str,
                       memory_enabled: bool = True, search_enabled: bool = True,
                       model: str = None) -> Dict:
        """
        处理用户消息 - 实现文档中的对话流程

        流程：
        1. 用户输入信息
        2. 构建prompt + 用户输入信息 给llm, 看需要查询什么记忆
        3. 按照llm提示查询本地记忆
        4. 本地记忆查询内容 + 用户输入信息 + 记忆提取promote 给到llm
        5. llm 返回记忆提取内容 以及 对用户输入信息的回复
        6. 本地服务更新记忆,如果有冲突以最新记忆为准

        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            content: 用户消息内容
            memory_enabled: 是否启用记忆
            search_enabled: 是否启用搜索
            model: 指定聊天模型（可选，默认动态解析/运行时切换值）

        Returns:
            响应字典
        """
        logger.info(f"[CHAT] 开始处理用户消息 - 用户:{user_id}, 会话:{session_id}, 指定模型:{model}")

        # ========== Step 1: 用户输入信息 ==========
        chat_logger.log_message_send(user_id, session_id, content)
        logger.info(f"[CHAT] Step 1: 用户输入信息 - 内容:{content[:100]}...")

        # ========== Step 2: 构建prompt + 用户输入信息 给llm, 看需要查询什么记忆 ==========
        logger.info("[CHAT] Step 2: 分析需要查询的记忆类型")
        analysis_result = memory_router.analyze_memory_need(content)
        logger.info(f"[CHAT]   记忆分析完成 - needs_query:{analysis_result.get('needs_memory_query', False)}, "
                   f"类型:{analysis_result.get('recommended_memory_types', [])}, "
                   f"关键词:{analysis_result.get('query_keywords', [])}")

        # ========== Step 3: 按照llm提示查询本地记忆 ==========
        memory_context = []
        if memory_enabled and analysis_result.get("needs_memory_query", False):
            logger.info("[CHAT] Step 3: 查询本地记忆")
            try:
                memory_context = memory_service.search_memories_by_analysis(
                    user_id=user_id,
                    analysis_result=analysis_result,
                    top_k=5
                )
                logger.info(f"[CHAT]   查询到 {len(memory_context)} 条相关记忆")
                for i, m in enumerate(memory_context[:3]):
                    logger.debug(f"[CHAT]   记忆{i+1}: {m.get('content', '')[:50]}... (相似度: {m.get('similarity', 0):.2f})")
            except Exception as e:
                logger.error(f"[CHAT]   查询记忆失败 - 错误:{e}")

        # ========== Step 4: 本地记忆查询内容 + 用户输入信息 + 记忆提取prompt 给到llm ==========
        logger.info("[CHAT] Step 4: 构建提取prompt并调用LLM")
        try:
            # 构建最终的完整prompt
            system_prompt = self._build_final_system_prompt(
                user_input=content,
                memory_context=memory_context,
                analysis_result=analysis_result
            )

            full_prompt = f"{system_prompt}\n\n用户: {content}\n\nAI:"

            # 调用LLM生成响应
            logger.info("[CHAT] Step 5: LLM生成响应")
            response_content = self.generate(full_prompt, system_prompt, model=model)
            logger.debug(f"[CHAT]   LLM响应长度:{len(response_content)}")

        except Exception as e:
            logger.error(f"[CHAT]   生成响应失败 - 错误:{e}")
            # 回退到简单响应
            system_prompt = "你是一个智能助手。请回答用户问题。"
            if memory_context:
                memory_text = "\n".join([f"- {m['content']} (相似度: {m['similarity']:.2f})" for m in memory_context])
                system_prompt += f"\n\n用户背景信息：\n{memory_text}"
            full_prompt = f"{system_prompt}\n\n用户: {content}\n\nAI:"
            response_content = self.generate(full_prompt, system_prompt, model=model)

        # ========== Step 5: LLM返回记忆提取内容以及对用户输入信息的回复 ==========
        logger.info("[CHAT] Step 6: 处理LLM响应并更新记忆")

        # 解析响应（尝试提取响应中的记忆信息）
        memory_updates = []
        if memory_enabled:
            try:
                # 使用记忆提取器从对话中提取新记忆
                extraction_result = memory_extractor.extract_memories(
                    user_input=content,
                    ai_response=response_content,
                    context_memories=memory_context
                )

                logger.info(f"[CHAT]   提取到 {extraction_result.get('extracted_count', 0)} 条新记忆")

                # ========== Step 6: 本地服务更新记忆,如果有冲突以最新记忆为准 ==========
                for mem_data in extraction_result.get("memories", []):
                    try:
                        logger.debug(f"[CHAT]   更新/创建记忆 - 内容:{mem_data.get('content', '')[:50]}..., 类型:{mem_data.get('type', '')}")
                        result = memory_service.update_or_create_memory(
                            user_id=user_id,
                            content=mem_data.get("content", ""),
                            memory_type=mem_data.get("type", "semantic"),
                            category=mem_data.get("category", "general"),
                            importance=mem_data.get("importance", 5)
                        )
                        # 添加action字段到记忆更新中
                        mem_data["action"] = result.get("action", "created")
                        memory_updates.append(mem_data)
                    except Exception as e:
                        logger.error(f"[CHAT]   更新/创建记忆失败 - 错误:{e}")

            except Exception as e:
                logger.error(f"[CHAT]   记忆处理失败 - 错误:{e}")

        # 存储用户消息
        user_msg = Message(
            session_id=session_id,
            role="user",
            content=content
        )
        self.db.add(user_msg)
        self.db.commit()
        logger.debug(f"[CHAT] 用户消息已存储")

        # 存储AI消息
        ai_msg = Message(
            session_id=session_id,
            role="assistant",
            content=response_content,
            raw_response=response_content
        )
        self.db.add(ai_msg)
        self.db.commit()
        logger.debug(f"[CHAT] AI消息已存储")

        logger.info(f"[CHAT] 处理完成 - 响应长度:{len(response_content)}, 新记忆:{len(memory_updates)}")
        chat_logger.log_ai_response(user_id, session_id, len(response_content), len(memory_updates))

        return {
            "response": response_content,
            "memory_updates": memory_updates,
            "memory_context": memory_context,
            "analysis_result": analysis_result,
            "tokens_used": len(response_content) // 4
        }

    def process_message_stream(self, user_id: int, session_id: int, content: str,
                       memory_enabled: bool = True, search_enabled: bool = True) -> AsyncGenerator[str, None]:
        """
        处理用户消息（流式）

        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            content: 用户消息内容
            memory_enabled: 是否启用记忆
            search_enabled: 是否启用搜索

        Yields:
            流式响应内容
        """
        # 构建记忆上下文
        memory_context = []
        if memory_enabled:
            memory_context = self.build_memory_context(
                user_id=user_id,
                query=content,
                top_k=3
            )

        # 构建搜索上下文
        search_context = None
        if search_enabled:
            search_context = self.build_search_context(content, memory_context)

        # 构建 prompt
        system_prompt = "你是一个智能助手。请回答用户问题。"

        if memory_context:
            memory_text = "\n".join([f"- {m['content']} (相似度: {m['similarity']:.2f})" for m in memory_context])
            system_prompt += f"\n\n用户背景信息（基于语义检索的记忆）：\n{memory_text}"

        if search_context and search_context.get("query"):
            system_prompt += f"\n\n搜索上下文：{search_context['query']}"

        full_prompt = f"{system_prompt}\n\n用户: {content}\n\nAI:"

        # 生成流式响应
        return ollama_service.generate(full_prompt, system_prompt, stream=True)


# 全局实例
chat_service = ChatService()
