"""
SunChat Backend - Chat Service with Logging
"""
import threading
import uuid
import json
import re
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

from app.config import settings
from core.llm import ollama_service
from core.embedding import embedding_service
from core.search import search_service
from core.chat_router import chat_router
from core.memory_router import memory_router
from core.memory_extractor import memory_extractor
from services.memory_service import memory_service
from models.sql_models import DBSessionMixin, ChatSession, Message
from models.schemas import MessageCreate, MemoryResponse
from utils.logger import chat_logger, memory_logger, logger


class ChatService(DBSessionMixin):
    """聊天服务（db 属性见 DBSessionMixin：线程本地 Session）"""

    def __init__(self):
        pass

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

    # ==================== 统一上下文构建（非流式/流式共用） ====================

    def get_recent_messages(self, session_id: int, n: int = None) -> List[Dict]:
        """取最近 n 条历史消息（时间正序），用于多轮上下文。"""
        n = n or settings.CHAT_HISTORY_MESSAGES
        rows = (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(n)
            .all()
        )
        rows = list(reversed(rows))
        return [{"role": m.role, "content": m.content} for m in rows
                if m.role in ("user", "assistant")]

    def build_context(self, user_id: int, session_id: int, content: str,
                      memory_enabled: bool = True, search_enabled: bool = True) -> Dict:
        """构建对话上下文：记忆路由/检索 + 搜索接入 + 多轮历史 + 单份 system。

        返回 {system_prompt, history, memory_context, analysis_result, sources}
        """
        # 记忆需求分析（规则优先：问候语等 0 LLM 调用）
        if memory_enabled:
            analysis_result = memory_router.analyze_memory_need(content)
            # M3 原文优先策略依赖 user_input 字段(LLM 路径可能回空), 兜底填充
            if not analysis_result.get("user_input"):
                analysis_result["user_input"] = content
        else:
            analysis_result = {"needs_memory_query": False,
                               "recommended_memory_types": [], "query_keywords": []}

        memory_context = []
        if memory_enabled and analysis_result.get("needs_memory_query", False):
            try:
                memory_context = memory_service.search_memories_by_analysis(
                    user_id=user_id, analysis_result=analysis_result,
                    top_k=settings.MEMORY_INJECT_TOPK)
                logger.info(f"[CHAT] 记忆注入 {len(memory_context)}条 "
                            f"top1_score={memory_context[0].get('final_score') if memory_context else '-'}")
            except Exception as e:
                logger.error(f"[CHAT] 查询记忆失败 - 错误:{e}")

        # 搜索接入：意图路由判定为 search 且开关开启时，执行搜索并归纳进 system
        sources: List[Dict] = []
        system_prompt = self._build_final_system_prompt(
            user_input=content, memory_context=memory_context,
            analysis_result=analysis_result)

        if search_enabled:
            # 行情直查优先：股价类问题直接拿权威数字，不经 DDG/意图路由
            try:
                from core.stock import is_stock_query, get_stock_context
                if is_stock_query(content):
                    stock_ctx = get_stock_context(content)
                    if stock_ctx:
                        system_prompt += f"\n\n{stock_ctx}\n请直接引用上述实时数字回答。"
                        sources.append({
                            "title": "腾讯行情（实时数据）", "url": "https://gu.qq.com/",
                            "source": "tencent-quote", "snippet": stock_ctx, "score": 1.0})
            except Exception as e:
                logger.warning(f"[CHAT] 行情直查失败（忽略）: {e}")

            # 天气直查优先：wttr.in 实时数据，命中则不再走 DDG（更快更准）
            weather_hit = False
            try:
                from core.weather import is_weather_query, get_weather_context
                if is_weather_query(content):
                    weather_ctx = get_weather_context(content)
                    if weather_ctx:
                        weather_hit = True
                        system_prompt += f"\n\n{weather_ctx}\n请直接引用上述实时天气数据回答。"
                        sources.append({
                            "title": "wttr.in（实时天气）", "url": "https://wttr.in/",
                            "source": "wttr-in", "snippet": weather_ctx, "score": 1.0})
            except Exception as e:
                logger.warning(f"[CHAT] 天气直查失败（忽略）: {e}")

            try:
                decision = ({"tool": None} if weather_hit else
                            chat_router.route(content, context={"memories": memory_context}))
                if decision.get("tool") == "search":
                    from services.search_service import search_svc
                    summary = search_svc.search_with_introduction(content, memory_context)
                    answer = summary.get("answer", "")
                    new_sources = summary.get("sources", [])
                    if answer and new_sources:
                        refs = "\n".join(
                            f"- {s.get('title', '')} ({s.get('url', '')})"
                            for s in new_sources[:3])
                        system_prompt += (
                            f"\n\n联网搜索结果（回答时请综合并在需要时注明来源）：\n{answer}\n"
                            f"来源：\n{refs}")
                    # 行情来源保持在首位，去重合并 DDG 来源
                    seen = {s["url"] for s in sources}
                    sources += [s for s in new_sources if s.get("url") not in seen]
            except Exception as e:
                logger.warning(f"[CHAT] 搜索接入失败（忽略）: {e}")

        return {
            "system_prompt": system_prompt,
            "history": self.get_recent_messages(session_id),
            "memory_context": memory_context,
            "analysis_result": analysis_result,
            "sources": sources,
        }

    def to_chat_messages(self, ctx: Dict, content: str) -> List[Dict]:
        """转成 Ollama /api/chat 消息序列：system 单份 + 多轮历史 + 当前输入。"""
        messages = [{"role": "system", "content": ctx["system_prompt"]}]
        messages += [{"role": m["role"], "content": m["content"]} for m in ctx["history"]]
        messages.append({"role": "user", "content": content})
        return messages

    def save_user_message(self, session_id: int, content: str) -> Message:
        msg = Message(session_id=session_id, role="user", content=content)
        self.db.add(msg)
        self.db.commit()
        return msg

    def save_assistant_message(self, session_id: int, content: str,
                               tokens_used: int = 0) -> Message:
        msg = Message(session_id=session_id, role="assistant", content=content,
                      raw_response=content, tokens_used=tokens_used)
        self.db.add(msg)
        self.db.commit()
        return msg

    def apply_memory_extraction(self, user_id: int, content: str,
                                response_content: str,
                                memory_context: List[Dict]) -> List[Dict]:
        """执行记忆提取并落库（冲突以新为准），返回 memory_updates 列表。"""
        memory_updates: List[Dict] = []
        try:
            extraction_result = memory_extractor.extract_memories(
                user_input=content,
                ai_response=response_content,
                context_memories=memory_context,
            )
            for mem_data in extraction_result.get("memories", []):
                try:
                    result = memory_service.update_or_create_memory(
                        user_id=user_id,
                        content=mem_data.get("content", ""),
                        memory_type=mem_data.get("type", "semantic"),
                        category=mem_data.get("category", "general"),
                        importance=mem_data.get("importance", 5),
                        confidence=mem_data.get("confidence", 0.5),
                    )
                    if result.get("action") == "rejected":
                        continue
                    mem_data["action"] = result.get("action", "created")
                    memory_updates.append(mem_data)
                except Exception as e:
                    logger.error(f"[CHAT] 更新/创建记忆失败 - 错误:{e}")
        except Exception as e:
            logger.error(f"[CHAT] 记忆处理失败 - 错误:{e}")
        return memory_updates

    def extract_memories_async(self, user_id: int, content: str,
                               response_content: str,
                               memory_context: List[Dict]):
        """后台守护线程执行记忆提取，不阻塞响应；失败只记日志。"""
        def _job():
            try:
                self.apply_memory_extraction(user_id, content, response_content,
                                             memory_context)
            except Exception as e:
                logger.error(f"[CHAT] 后台记忆提取失败: {e}")
            finally:
                # 释放本后台线程的 Session，避免连接泄漏
                try:
                    from models.sql_models import reset_thread_session
                    reset_thread_session()
                except Exception:
                    pass

        t = threading.Thread(target=_job, name="memory-extractor", daemon=True)
        t.start()
        return t

    def process_message(self, user_id: int, session_id: int, content: str,
                       memory_enabled: bool = True, search_enabled: bool = True,
                       model: str = None, extract_memory_inline: bool = False) -> Dict:
        """
        处理用户消息（优化后流程）:
        1. 构建上下文：规则优先记忆路由 → 记忆检索 → 可选搜索接入 → 多轮历史
        2. system 单份注入，LLM 生成一次（真实 token 计数；失败抛出不吞）
        3. 落库 user + assistant(含 tokens_used)
        4. 记忆提取默认异步（后台线程），extract_memory_inline=True 时同步执行

        Args / Returns: 同原接口，另 memory_updates 在异步模式下为 []（稍后落库）。
        """
        logger.info(f"[CHAT] 开始处理用户消息 - 用户:{user_id}, 会话:{session_id}, 指定模型:{model}")
        chat_logger.log_message_send(user_id, session_id, content)

        ctx = self.build_context(user_id, session_id, content,
                                 memory_enabled=memory_enabled,
                                 search_enabled=search_enabled)
        messages = self.to_chat_messages(ctx, content)

        raw = ollama_service.chat(messages, model=model)
        response_content = raw.get("message", {}).get("content", "")
        tokens_used = raw.get("eval_count", 0)
        if not response_content:
            raise RuntimeError("LLM 返回空内容（服务可能不可用）")

        self.save_user_message(session_id, content)
        self.save_assistant_message(session_id, response_content, tokens_used)

        if memory_enabled:
            if extract_memory_inline:
                memory_updates = self.apply_memory_extraction(
                    user_id, content, response_content, ctx["memory_context"])
            else:
                self.extract_memories_async(
                    user_id, content, response_content, ctx["memory_context"])
                memory_updates = []
        else:
            memory_updates = []

        logger.info(f"[CHAT] 处理完成 - 响应长度:{len(response_content)}, tokens:{tokens_used}")
        chat_logger.log_ai_response(user_id, session_id, len(response_content),
                                    len(memory_updates))

        return {
            "response": response_content,
            "memory_updates": memory_updates,
            "memory_context": ctx["memory_context"],
            "analysis_result": ctx["analysis_result"],
            "sources": ctx["sources"],
            "tokens_used": tokens_used
        }

    # ==================== 会话管理（S6：真实落库） ====================

    def rename_session(self, session_id: int, title: str) -> bool:
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.deleted_at == None  # noqa: E711
        ).first()
        if not session:
            return False
        session.title = title
        self.db.commit()
        return True

    def delete_session(self, session_id: int) -> bool:
        """软删除（与 list_sessions 的 deleted_at == None 过滤一致）。"""
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.deleted_at == None  # noqa: E711
        ).first()
        if not session:
            return False
        session.deleted_at = datetime.now()
        self.db.commit()
        return True

    # ==================== 流式（S5 共用上下文构建） ====================

    def stream_reply(self, ctx: Dict, content: str, model: str = None):
        """按上下文流式生成（同步 generator，逐块 yield 文本）。"""
        return ollama_service.chat_stream(self.to_chat_messages(ctx, content),
                                          model=model)

    def finalize_stream(self, user_id: int, session_id: int, content: str, full: str,
                        ctx: Dict, memory_enabled: bool = True):
        """流结束收尾：存 assistant 消息 + 后台记忆提取。"""
        self.save_assistant_message(
            session_id, full, tokens_used=max(1, len(full) // 4))
        if memory_enabled:
            self.extract_memories_async(user_id, content, full, ctx["memory_context"])
        chat_logger.log_ai_response(user_id, session_id, len(full), 0)


# 全局实例
chat_service = ChatService()
