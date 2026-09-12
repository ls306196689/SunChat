"""
SunChat Backend - Chat Service with Logging
"""
import base64
import contextvars
import threading
import time
import uuid
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, AsyncGenerator, Tuple
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
from utils.logger import chat_logger, memory_logger, logger, log_event


# ==================== R-008: 对话图片工具 ====================

_IMG_B64_TTL = 60  # base64 读取缓存秒数（同 stock TTL 语义）
_IMG_B64_CACHE: Dict[str, Tuple[float, str]] = {}
_IMG_CACHE_LOCK = threading.Lock()


def image_b64(image_id: str) -> Optional[str]:
    """读对话图片文件 → base64 文本（带 TTL 缓存）；文件缺失/不可读 → None。"""
    with _IMG_CACHE_LOCK:
        hit = _IMG_B64_CACHE.get(image_id)
        if hit and time.monotonic() - hit[0] < _IMG_B64_TTL:
            return hit[1]
    import app.config as _cfg  # 运行时读取(reload 兼容,同 sql_models 模式)
    path = Path(_cfg.settings.CHAT_IMAGE_DIR) / image_id
    if not path.is_file():
        return None
    try:
        data = base64.b64encode(path.read_bytes()).decode()
    except OSError as e:
        logger.warning(f"[CHAT] 图片读取失败 {image_id}: {e}")
        return None
    with _IMG_CACHE_LOCK:
        _IMG_B64_CACHE[image_id] = (time.monotonic(), data)
    return data


class ChatService(DBSessionMixin):
    """聊天服务（db 属性见 DBSessionMixin：线程本地 Session）"""

    # R-007: 记忆提取有界池（实例级惰性；上限可在测试覆盖）
    _extract_workers = 2
    _extract_max_inflight = 8

    def __init__(self):
        self._extract_lock = threading.Lock()
        self._extract_inflight = 0
        self._extract_pool = None

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
                    "images": json.loads(msg.images or "[]"),  # R-008
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
        return [{"role": m.role, "content": m.content,
                 "images": json.loads(m.images or "[]")}  # R-008: 上下文窗口带图
                for m in rows if m.role in ("user", "assistant")]

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
            stock_hit = False
            from services.search_service import _UNSET
            _stock_probe = _UNSET  # R-006: 记录探测结果透传去重(None=已试失败)
            try:
                from core.stock import is_stock_query, get_stock_context
                if is_stock_query(content):
                    stock_ctx = get_stock_context(content)
                    _stock_probe = stock_ctx
                    if stock_ctx:
                        stock_hit = True
                        system_prompt += f"\n\n{stock_ctx}\n请直接引用上述实时数字回答。"
                        sources.append({
                            "title": "腾讯行情（实时数据）", "url": "https://gu.qq.com/",
                            "source": "tencent-quote", "snippet": stock_ctx, "score": 1.0})
            except Exception as e:
                _stock_probe = None  # R-006: 异常同样计"已试失败",下游不再重复请求
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
                decision = ({"tool": None} if (weather_hit or stock_hit) else
                            chat_router.route(content, context={"memories": memory_context}))
                if decision.get("tool") == "search":
                    from services.search_service import search_svc
                    summary = search_svc.search_with_introduction(
                        content, memory_context, stock_context=_stock_probe)
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

    def to_chat_messages(self, ctx: Dict, content: str,
                         images: List[str] = None,
                         ) -> List[Dict]:
        """转成 Ollama /api/chat 消息序列：system 单份 + 多轮历史 + 当前输入。

        R-008: images（当前附图 image_id 列表）注入当前 user 消息 base64；
        历史窗口内带图消息（最近 CHAT_IMAGE_WINDOW_MSGS 条、每条≤CHAT_IMAGE_MAX_PER_MSG、
        总≤CHAT_IMAGE_TOTAL_MAX 含当前）注入历史 base64；
        非 vision 模型自动 strip（D-402）。
        时序注:build_context 先于 save_user_message,故 history 不含当前消息,无需去重。
        """
        messages = [{"role": "system", "content": ctx["system_prompt"]}]
        cur_imgs = list(images or [])[:settings.CHAT_IMAGE_MAX_PER_MSG]

        # 历史窗口收集（仅 user 带图消息,从新到旧;流式路径跳过已落库的当前消息）
        hist = ctx["history"]
        budget = max(settings.CHAT_IMAGE_TOTAL_MAX - len(cur_imgs), 0)
        hist_b64: Dict[int, List[str]] = {}  # history索引 → b64列表（从新到旧消费预算）
        window_imgs: List[Tuple[int, List[str]]] = []
        for idx in range(len(hist) - 1, -1, -1):
            m = hist[idx]
            m_imgs = m.get("images") or []
            if m["role"] == "user" and m_imgs:
                window_imgs.append((idx, m_imgs[:settings.CHAT_IMAGE_MAX_PER_MSG]))
                if len(window_imgs) >= settings.CHAT_IMAGE_WINDOW_MSGS:
                    break
        for idx, m_imgs in window_imgs:
            if budget <= 0:
                break
            take = m_imgs[:budget]
            budget -= len(take)
            hist_b64[idx] = [b for iid in take
                             if (b := image_b64(iid)) is not None]

        for idx, m in enumerate(hist):
            msg = {"role": m["role"], "content": m["content"]}
            if idx in hist_b64 and hist_b64[idx]:
                msg["images"] = hist_b64[idx]
            messages.append(msg)

        user_msg: Dict = {"role": "user", "content": content}
        if cur_imgs:
            b64s = [b for iid in cur_imgs if (b := image_b64(iid)) is not None]
            if b64s:
                user_msg["images"] = b64s
        messages.append(user_msg)

        # 非 vision 模型：剥离全部 images（可用性优先，D-402）
        if any("images" in m for m in messages):
            from core.model_manager import model_manager
            if not model_manager.supports_vision():
                logger.warning("[CHAT] 当前模型不支持 vision，本请求图片已剥离（仅文字）")
                for m in messages:
                    m.pop("images", None)
        return messages

    def save_user_message(self, session_id: int, content: str,
                          images: List[str] = None) -> Message:
        msg = Message(session_id=session_id, role="user", content=content,
                      images=json.dumps(list(images or [])))
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
                    logger.error(f"[CHAT] 更新/创建记忆失败 - 错误:{e}", exc_info=True)
            log_event(logger, "memory", "extract", "ok", saved=len(memory_updates))
        except Exception as e:
            log_event(logger, "memory", "extract", "fail",
                      error=str(e)[:120], exc=True)
        return memory_updates

    def extract_memories_async(self, user_id: int, content: str,
                               response_content: str,
                               memory_context: List[Dict]):
        """R-007: 有界线程池执行记忆提取（max_workers=2,在途≤8）,不阻塞响应；
        超限丢弃记 WARNING（主链路优先,记忆可后补）;失败只记日志。
        R-013: copy_context 包裹任务,后台线程继承请求 trace(AC-1)。"""
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
                with self._extract_lock:
                    self._extract_inflight -= 1

        with self._extract_lock:
            if self._extract_inflight >= self._extract_max_inflight:
                logger.warning(
                    f"[CHAT] 记忆提取队列已满(在途{self._extract_inflight}),"
                    f"本条丢弃 - user:{user_id}")
                return None
            self._extract_inflight += 1
            if self._extract_pool is None:
                from concurrent.futures import ThreadPoolExecutor
                self._extract_pool = ThreadPoolExecutor(
                    max_workers=self._extract_workers,
                    thread_name_prefix="memory-extractor")
            ctx = contextvars.copy_context()  # R-013: trace 继承进线程池
            return self._extract_pool.submit(ctx.run, _job)

    def process_message(self, user_id: int, session_id: int, content: str,
                       memory_enabled: bool = True, search_enabled: bool = True,
                       model: str = None, extract_memory_inline: bool = False,
                       images: List[str] = None) -> Dict:
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
        messages = self.to_chat_messages(ctx, content, images=images)

        raw = ollama_service.chat(messages, model=model)
        response_content = raw.get("message", {}).get("content", "")
        tokens_used = raw.get("eval_count", 0)
        if not response_content:
            raise RuntimeError("LLM 返回空内容（服务可能不可用）")

        self.save_user_message(session_id, content, images=images)
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

    def stream_reply(self, ctx: Dict, content: str, model: str = None,
                     images: List[str] = None):
        """按上下文流式生成（同步 generator，逐块 yield 文本）。R-008: 支持附图。"""
        return ollama_service.chat_stream(self.to_chat_messages(ctx, content,
                                                                images=images),
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
