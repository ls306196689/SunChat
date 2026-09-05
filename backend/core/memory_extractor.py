"""
SunChat Backend - Memory Extractor
从对话中提取记忆并构建提取prompt
"""
from typing import List, Dict, Optional
from datetime import datetime

from core.llm import ollama_service
from utils.json_parser import parse_json_response
from utils.logger import logger


class MemoryExtractor:
    """
    记忆提取器 - 从对话中提取有价值的记忆

    流程：
    1. 接收用户输入和AI响应
    2. 构建记忆提取prompt
    3. 调用LLM提取记忆
    4. 返回提取的记忆列表
    """

    def __init__(self):
        self.default_category_map = {
            "preference": "preference",
            "person": "person",
            "event": "event",
            "knowledge": "knowledge",
            "relationship": "relationship",
            "habit": "habit",
            "general": "general"
        }

    def extract_memories(self, user_input: str, ai_response: str, context_memories: List[Dict] = None) -> Dict:
        """
        从对话中提取记忆

        Args:
            user_input: 用户输入
            ai_response: AI响应
            context_memories: 上下文记忆（可选）

        Returns:
            提取结果：
            {
                "memories": [...],  // 提取的记忆列表
                "summary": "提取摘要",
                "confidence": 0.8,  // 置信度
                "extracted_count": 3  // 提取数量
            }
        """
        logger.info(f"[MEMORY_EXTRACTOR] 开始提取记忆 - 用户输入长度:{len(user_input)}, AI响应长度:{len(ai_response)}")

        # 构建提取prompt
        prompt = self._build_extraction_prompt(user_input, ai_response, context_memories)

        try:
            # 调用LLM
            response = ollama_service.generate(prompt)

            logger.debug(f"[MEMORY_EXTRACTOR] LLM原始响应: {response[:500]}")

            # 解析响应
            result = self._parse_extraction_response(response)

            logger.info(f"[MEMORY_EXTRACTOR] 记忆提取完成 - 提取数量:{result['extracted_count']}, 置信度:{result['confidence']}")

            return result

        except Exception as e:
            logger.error(f"[MEMORY_EXTRACTOR] 提取失败 - 错误:{e}")
            return {
                "memories": [],
                "summary": "提取失败",
                "confidence": 0.0,
                "extracted_count": 0,
                "error": str(e)
            }

    def _build_extraction_prompt(self, user_input: str, ai_response: str, context_memories: List[Dict] = None) -> str:
        """构建记忆提取prompt"""
        # 构建上下文记忆部分
        context_text = ""
        if context_memories:
            context_text = "\n\n相关上下文记忆：\n"
            for i, mem in enumerate(context_memories[:5], 1):
                context_text += f"{i}. {mem.get('content', '')}\n"

        return f"""你是一个智能记忆提取器。请从以下对话中提取对用户有价值的记忆信息。

用户输入: {user_input}
AI响应: {ai_response}{context_text}

请以 JSON 格式输出提取的记忆，格式如下：
{{
    "memories": [
        {{
            "content": "提取的记忆内容（完整、明确的陈述）",
            "type": "semantic/episodic",
            "category": "preference/person/event/knowledge/relationship/habit/general",
            "importance": 1-10,
            "source": "user_message/ai_response/direct_statement",
            "confidence": 0.5-1.0
        }}
    ],
    "summary": "提取摘要",
    "confidence": 0.0-1.0
}}

要求：
1. **优先从用户输入中提取明确的事实信息**
2. 用户主动告诉你的信息（如名字、偏好、背景）是重要的记忆
3. 用户描述的事实、观点、经历都应提取
4. 即使是简单的陈述，只要包含有用信息就提取
5. 如果用户提供了名字，必须以"用户叫[名字]"格式存储，重要性必须是 10
6. 对于用户提问，如果提问本身透露了信息（如"我叫什么"暗示用户想提供名字），也应提取
7. 如果对话中提到具体的时间（昨天、今天、最近等），应该在记忆中保留时间信息
8. 如果AI响应中提供了重要的信息或建议，且用户表示接受或认同，可以提取
9. 即使没有明确的个人相关信息，如果对话中有任何有用的信息，也应提取
10. 如果确实没有任何有效信息，返回空数组 []
11. source 字段指示记忆来源：user_message(用户消息), ai_response(AI响应), direct_statement(直接陈述)
12. confidence 字段表示提取的置信度
13. 请直接输出 JSON，不要有任何额外文本（不要用```json包围）。
"""

    def _parse_extraction_response(self, response: str) -> Dict:
        """解析LLM提取响应（统一走 utils.json_parser，G7）"""
        result = parse_json_response(response)
        if result is None:
            logger.error("[MEMORY_EXTRACTOR] JSON解析失败")
            logger.debug(f"[MEMORY_EXTRACTOR] 原始响应: {response[:300]}")
            # 尝试从文本中提取信息
            return self._fallback_parse(response)

        # 标准化输出格式
        memories = result.get("memories", [])
        if not isinstance(memories, list):
            memories = []

        # 标准化每条记忆的格式
        normalized_memories = []
        for mem in memories:
            normalized_mem = self._normalize_memory(mem)
            if normalized_mem:
                normalized_memories.append(normalized_mem)

        # 确定总置信度
        confidence = result.get("confidence", 0.5)
        if normalized_memories:
            avg_conf = sum(m.get("confidence", 0.5) for m in normalized_memories) / len(normalized_memories)
            confidence = max(confidence, avg_conf)

        return {
            "memories": normalized_memories,
            "summary": result.get("summary", f"提取了 {len(normalized_memories)} 条记忆"),
            "confidence": min(1.0, confidence),
            "extracted_count": len(normalized_memories),
        }

    def _normalize_memory(self, mem: Dict) -> Optional[Dict]:
        """标准化记忆格式"""
        try:
            content = mem.get("content", "").strip()
            if not content:
                return None

            return {
                "content": content,
                "type": mem.get("type", "semantic"),
                "category": mem.get("category", "general"),
                "importance": min(10, max(1, mem.get("importance", 5))),
                "source": mem.get("source", "user_message"),
                "confidence": min(1.0, max(0.5, mem.get("confidence", 0.5)))
            }
        except Exception as e:
            logger.debug(f"[MEMORY_EXTRACTOR] 标准化记忆失败: {e}")
            return None

    def _fallback_parse(self, response: str) -> Dict:
        """回退解析方案（当JSON解析失败时）"""
        import re

        # 尝试提取可能的记忆
        memories = []
        confidence = 0.3

        # 查找类似"用户叫XXX"的模式
        name_pattern = r"用户叫\s*([\\w\\u4e00-\\u9fa5]+)"
        name_match = re.search(name_pattern, response, re.IGNORECASE)
        if name_match:
            memories.append({
                "content": f"用户叫{name_match.group(1)}",
                "type": "semantic",
                "category": "person",
                "importance": 10,
                "source": "ai_response",
                "confidence": 0.9
            })
            confidence = 0.6

        # 查找类似"喜欢XXX"的模式
        like_pattern = r"(喜欢|讨厌|爱|不爱)\\s*([^。！？]+)"
        like_matches = re.findall(like_pattern, response, re.IGNORECASE)
        for match in like_matches[:3]:  # 最多3条
            memories.append({
                "content": match[0] + match[1].strip(),
                "type": "semantic",
                "category": "preference",
                "importance": 5,
                "source": "ai_response",
                "confidence": 0.5
            })
            confidence = max(confidence, 0.4)

        return {
            "memories": memories,
            "summary": f"提取了 {len(memories)} 条记忆（回退解析）",
            "confidence": confidence,
            "extracted_count": len(memories)
        }


# 全局实例
memory_extractor = MemoryExtractor()
