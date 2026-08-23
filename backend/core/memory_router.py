"""
SunChat Backend - Memory Router
根据用户输入决定需要查询/提取什么记忆
"""
import json
from typing import List, Dict, Optional
from datetime import datetime

from core.llm import ollama_service
from utils.logger import logger


class MemoryRouter:
    """
    记忆路由器 - 决定需要查询什么记忆

    流程：
    1. 接收用户输入
    2. 让LLM分析需要查询什么类型的记忆
    3. 返回记忆查询参数
    """

    def __init__(self):
        # 记忆类型定义
        self.memory_types = [
            {
                "type": "preference",
                "description": "用户偏好和喜好",
                "keywords": ["喜欢", "讨厌", "喜欢的", "爱", "不爱", "偏好", "倾向"]
            },
            {
                "type": "person",
                "description": "个人信息（名字、年龄、职业等）",
                "keywords": ["我叫", "我的名字", "我是", "年龄", "职业", "工作", "身份", "我是谁", "谁"]
            },
            {
                "type": "event",
                "description": "用户经历的事件",
                "keywords": ["昨天", "今天", "最近", "之前", "上次", "刚才", "事件", "经历"]
            },
            {
                "type": "knowledge",
                "description": "用户分享的知识和事实",
                "keywords": ["知道", "记得", "忘记", "记得吗", "我告诉你", "事实", "什么是"]
            },
            {
                "type": "relationship",
                "description": "人际关系信息",
                "keywords": ["朋友", "家人", "同事", "老板", "同学", "认识", "认识谁"]
            },
            {
                "type": "habbit",
                "description": "习惯和日常行为",
                "keywords": ["习惯", "总是", "经常", "每天", "每周", "习惯性"]
            }
        ]

    def analyze_memory_need(self, user_input: str, context: Dict = None) -> Dict:
        """
        分析用户输入，确定需要查询什么记忆

        Args:
            user_input: 用户输入内容
            context: 上下文信息（包含之前的对话）

        Returns:
            记忆查询分析结果
        """
        # 使用LLM分析用户输入
        prompt = self._build_analysis_prompt(user_input, context)

        try:
            # 调用LLM获取分析结果
            response = ollama_service.generate(prompt)

            logger.debug(f"[MEMORY_ROUTER] LLM原始响应: {response[:500]}")

            # 解析LLM响应
            analysis_result = self._parse_analysis_response(response)
            logger.info(f"[MEMORY_ROUTER] LLM分析完成 - 类型:{analysis_result.get('recommended_memory_types', [])}, "
                       f"关键词:{analysis_result.get('query_keywords', [])}")

        except Exception as e:
            logger.error(f"[MEMORY_ROUTER] LLM分析失败 - 错误:{e}，使用回退规则")
            # 使用规则回退方案
            analysis_result = self._fallback_analysis(user_input)

        return analysis_result

    def _build_analysis_prompt(self, user_input: str, context: Dict = None) -> str:
        """构建记忆需求分析prompt"""
        context_text = ""
        if context and context.get("conversation_history"):
            context_text = "\n\n对话历史：\n"
            for msg in context["conversation_history"][-3:]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_text += f"{role}: {content}\n"

        return f"""你是一个智能记忆分析器。请分析用户输入，判断需要查询什么类型的记忆。

用户输入: {user_input}{context_text}

请以 JSON 格式输出分析结果：
{{
    "needs_memory": true/false,
    "memory_types": ["type1", "type2"],  // 从以下类型中选择：preference(偏好), person(个人信息), event(事件), knowledge(知识), relationship(关系), habbit(习惯), general(通用)
    "query_keywords": ["关键词1", "关键词2"],  // 用于记忆检索的关键词，应该是2-5个相关词
    "confidence": 0.0-1.0,  // 分析置信度
    "notes": "分析说明"
}}

要求：
1. 如果用户输入包含个人信息（名字、喜好、背景等）或询问自己的信息，needs_memory 应为 true
2. 如果用户询问"我是谁"、"我叫什么"、"我的XXX"等，memory_types 应包含 "person"
3. 如果用户描述事实或分享知识，memory_types 应包含 "knowledge"
4. 如果用户询问关于自己过去的事情（昨天、今天、最近），memory_types 应包含 "event"
5. 如果用户询问偏好或喜好，memory_types 应包含 "preference"
6. 如果用户询问人际关系，memory_types 应包含 "relationship"
7. 如果用户询问习惯，memory_types 应包含 "habbit"
8. query_keywords 应该是2-5个相关关键词，用于向量搜索，优先提取名词和关键信息
9. 如果不确定，confidence 设为较低值（0.3-0.5）
10. 请直接输出 JSON，不要有任何额外文本。
"""

    def _parse_analysis_response(self, response: str) -> Dict:
        """解析LLM分析响应"""
        # 清理响应
        clean_response = response.strip()

        # 移除可能的Markdown代码块标记
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.startswith("```"):
            clean_response = clean_response[3:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]

        clean_response = clean_response.strip()

        # 尝试解析JSON
        try:
            result = json.loads(clean_response)

            # 标准化输出格式
            memory_types = result.get("memory_types", [])
            if not isinstance(memory_types, list):
                memory_types = []

            query_keywords = result.get("query_keywords", [])
            if not isinstance(query_keywords, list):
                query_keywords = []

            # 确定置信度
            confidence = result.get("confidence", 0.5)
            if not isinstance(confidence, (int, float)):
                confidence = 0.5

            return {
                "user_input": "",  # 将在调用处设置
                "analysis": {
                    "needs_memory": result.get("needs_memory", True),
                    "reason": result.get("notes", "LLM分析"),
                    "confidence": confidence
                },
                "recommended_memory_types": memory_types,
                "query_keywords": query_keywords,
                "needs_memory_query": result.get("needs_memory", True),
                "confidence": confidence
            }

        except json.JSONDecodeError as e:
            logger.error(f"[MEMORY_ROUTER] JSON解析失败: {e}")
            return self._fallback_analysis(clean_response)

    def _fallback_analysis(self, user_input: str) -> Dict:
        """回退分析方案（当LLM分析失败时）"""
        input_lower = user_input.lower()

        # 检查是否需要记忆
        memory_indicators = [
            "我", "我的", "我的名字", "我喜欢", "我讨厌", "我是",
            "记得", "忘记", "之前", "上次", "昨天", "今天",
            "我的朋友", "我的家人", "我的习惯", "我是谁", "谁"
        ]

        has_memory_need = any(indicator in user_input for indicator in memory_indicators)

        # 如果不需要记忆，返回简单结果
        if not has_memory_need:
            return {
                "user_input": user_input,
                "analysis": {
                    "needs_memory": False,
                    "reason": "用户输入不包含个人相关信息",
                    "confidence": 0.8
                },
                "recommended_memory_types": [],
                "query_keywords": [],
                "needs_memory_query": False,
                "confidence": 0.8
            }

        # 使用规则推荐类型
        memory_types = self._recommend_memory_types(user_input)

        # 如果没有匹配到任何类型，默认为 general
        if not memory_types:
            memory_types = ["general"]

        return {
            "user_input": user_input,
            "analysis": {
                "needs_memory": True,
                "reason": "规则分析匹配到个人相关信息",
                "confidence": 0.6
            },
            "recommended_memory_types": memory_types,
            "query_keywords": self._extract_keywords(user_input, memory_types),
            "needs_memory_query": True,
            "confidence": 0.6
        }

    def _recommend_memory_types(self, user_input: str) -> List[str]:
        """推荐需要查询的记忆类型"""
        recommended = []

        # 特殊处理"我是谁"、"我叫什么"等询问类问题（优先级最高）
        if any(q in user_input for q in ["我是谁", "我叫什么", "你知道我"]):
            if "person" not in recommended:
                recommended.append("person")

        # 检查其他类型
        for mt in self.memory_types:
            # 跳过已经添加的类型
            if mt["type"] == "person" and "person" in recommended:
                continue

            for keyword in mt["keywords"]:
                if keyword in user_input:
                    # 特殊处理"知道"关键词，避免匹配"你知道"
                    if keyword == "知道" and "你知道" in user_input:
                        # 检查是否是询问"你知道我"，这种情况已经由上面的规则处理
                        if "你知道我" not in user_input:
                            # 如果只是单纯说"我知道..."，则匹配knowledge类型
                            if not any(q in user_input for q in ["我是谁", "我叫什么"]):
                                if mt["type"] not in recommended:
                                    recommended.append(mt["type"])
                        break
                    # 特殊处理"记得"关键词
                    elif keyword == "记得" and "记得吗" in user_input:
                        if mt["type"] not in recommended:
                            recommended.append(mt["type"])
                        break
                    # 特殊处理"忘记"关键词
                    elif keyword == "忘记" and "忘记了" in user_input:
                        if mt["type"] not in recommended:
                            recommended.append(mt["type"])
                        break
                    # 普通关键词匹配
                    elif keyword not in ["知道", "记得", "忘记"]:
                        if mt["type"] not in recommended:
                            recommended.append(mt["type"])
                        break

        return recommended

    def _extract_keywords(self, user_input: str, memory_types: List[str]) -> List[str]:
        """从用户输入中提取关键词"""
        # 移除常见的停用词
        stopwords = {"的", "了", "在", "是", "我", "你", "他", "她", "它", "们", "有", "就", "都", "那", "这", "对", "是", "什么", "吗", "呢"}

        # 按空格和标点分割
        import re
        words = re.findall(r'[一-龥]+|[a-zA-Z]+', user_input)

        # 过滤停用词和太短的词
        keywords = [w for w in words if len(w) >= 2 and w not in stopwords]

        # 限制关键词数量
        return keywords[:5] if keywords else ["用户输入"]

    def get_memory_types(self) -> List[Dict]:
        """获取所有记忆类型定义"""
        return self.memory_types


# 全局实例
memory_router = MemoryRouter()
