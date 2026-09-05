"""
SunChat Backend - Agent LLM Interface
Ollama 原生 function-calling 客户端（复用 core.llm 统一 HTTP 会话，修 A2/A3/A4）。
"""
import json
from typing import List, Dict, Optional

from core.llm import _http
from core.model_manager import model_manager
from app.config import settings
from utils.logger import logger


class AgentLLM:
    """Agent LLM 通信接口（模型动态解析；透传 tools/tool_calls）"""

    def __init__(self, model: str = None, temperature: float = 0.7):
        self._fixed_model = model
        self.temperature = temperature

    def _resolve_model(self) -> str:
        if self._fixed_model:
            return self._fixed_model
        return model_manager.resolve_chat_model()

    def generate(self, messages: List[Dict], tools: List[Dict] = None,
                 stream: bool = False, model: Optional[str] = None) -> Dict:
        """调用 /api/chat，返回 {message: {role, content[, tool_calls]}, ...}。

        tool_calls 原样透传（Ollama 已兼容 OpenAI 格式），失败抛异常。
        """
        url = f"{settings.LLM_API_URL.rstrip('/')}/api/chat"
        payload = {
            "model": model or self._resolve_model(),
            "messages": messages,
            "temperature": self.temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        resp = _http.post(url, json=payload, timeout=settings.LLM_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        msg = result.get("message", {}) or {}
        out = {
            "message": {
                "role": msg.get("role", "assistant"),
                "content": msg.get("content", ""),
            },
            "model": result.get("model", payload["model"]),
        }
        if msg.get("tool_calls"):
            out["message"]["tool_calls"] = msg["tool_calls"]
        return out

    def supports_tools(self) -> bool:
        """能力探测（启发式）：模型名命中已知支持 tool calling 的系列才走工具循环。

        未知模型按"不确定"处理由上层降级；Ollama 对不支持 tools 的模型会直接忽略
        tools 字段返回纯文本，因此上层同时具备纯文本回退路径。
        """
        name = self._resolve_model().lower()
        known = ["qwen2.5", "qwen3", "qwen3.5", "qwen3.8", "llama3.1", "llama3.2",
                 "llama3.3", "glm4", "mistral", "mistral-nemo", "command-r",
                 "deepseek-r1", "gemma3", "firefunction"]
        return any(k in name for k in known)


# 全局实例
agent_llm = AgentLLM()
