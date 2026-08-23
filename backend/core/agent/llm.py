"""
SunChat Backend - Agent LLM Interface
与大语言模型通信的接口，负责格式化请求和解析响应
"""
import json
import re
import requests
from typing import List, Dict, Optional, Any

from core.llm import ollama_service
from core.model_manager import model_manager
from app.config import settings
from utils.logger import logger


class AgentLLM:
    """Agent LLM 通信接口（模型动态解析，URL 来自配置）"""

    def __init__(self, model: str = None, temperature: float = 0.7):
        # 显式指定的模型（可选），否则每次动态解析
        self._fixed_model = model
        self.temperature = temperature

    def _resolve_model(self) -> str:
        if self._fixed_model:
            return self._fixed_model
        return model_manager.resolve_chat_model()

    def generate(self, messages: List[Dict], tools: List[Dict] = None, stream: bool = False) -> Dict:
        """
        生成文本（支持工具调用）

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            tools: 工具定义列表
            stream: 是否流式返回

        Returns:
            LLM 响应
        """
        try:
            resolved_model = self._resolve_model()
            url = f"{settings.LLM_API_URL.rstrip('/')}/api/chat"
            payload = {
                "model": resolved_model,
                "messages": messages,
                "temperature": self.temperature,
                "stream": stream
            }

            if tools:
                payload["tools"] = tools

            # 调用 Ollama 服务
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            return {
                "message": {
                    "content": result.get("message", {}).get("content", ""),
                    "role": result.get("message", {}).get("role", "assistant")
                },
                "model": result.get("model", resolved_model),
                "done": result.get("done", True)
            }

        except Exception as e:
            logger.error(f"[AGENT_LLM] LLM 调用失败 - 错误:{e}")
            return {
                "error": str(e),
                "content": "LLM 调用失败，请稍后重试"
            }

    def parse_thought_action(self, text: str) -> Dict:
        """
        解析 Agent 的 Thought-Action 输出

        Args:
            text: LLM 原始输出

        Returns:
            解析后的 thought 和 action
        """
        result = {
            "thought": text,
            "action": None,
            "observation": None,
            "raw": text
        }

        # 尝试解析 JSON
        try:
            # 移除可能的 Markdown 代码块
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            # 尝试解析 JSON
            parsed = json.loads(clean_text)

            if isinstance(parsed, dict):
                result["thought"] = parsed.get("thought", text)
                result["action"] = parsed.get("action")
                result["observation"] = parsed.get("observation")
        except json.JSONDecodeError:
            # 如果不是 JSON，提取可能的 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    if isinstance(parsed, dict):
                        result["thought"] = parsed.get("thought", text)
                        result["action"] = parsed.get("action")
                        result["observation"] = parsed.get("observation")
                except json.JSONDecodeError:
                    pass

        return result

    def build_messages(
        self,
        system_prompt: str,
        conversation_history: List[Dict],
        user_input: str,
        tool_results: List[Dict] = None
    ) -> List[Dict]:
        """
        构建消息列表

        Args:
            system_prompt: 系统提示
            conversation_history: 对话历史
            user_input: 用户输入
            tool_results: 工具结果

        Returns:
            消息列表
        """
        messages = []

        # 添加系统提示
        messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史
        messages.extend(conversation_history)

        # 添加工具结果（如果有）
        if tool_results:
            for tool_result in tool_results:
                messages.append({
                    "role": "tool",
                    "content": json.dumps(tool_result, ensure_ascii=False),
                    "name": tool_result.get("tool_name", "tool")
                })

        # 添加用户输入
        messages.append({"role": "user", "content": user_input})

        return messages


# 全局实例
agent_llm = AgentLLM()
