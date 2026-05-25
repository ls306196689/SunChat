"""
SunChat Backend - LLM Service (Ollama)
"""
import requests
from typing import List, Dict, Optional
from app.config import settings


class OllamaService:
    """Ollama LLM 服务封装"""

    # 常见的聊天模型名称前缀
    CHAT_MODEL_PREFIXES = ["qwen", "llama", "glm", "deepseek", "mistral", "yi"]

    def __init__(self, api_url: str = None, model: str = None):
        self.api_url = api_url or settings.LLM_API_URL
        self.base_url = f"{self.api_url.rstrip('/')}"
        # 动态获取本地运行的模型，使用支持聊天的模型作为默认值
        self.model = model or self._get_chat_model()

    def _get_available_models(self) -> List[Dict]:
        """获取 Ollama 本地运行的模型列表"""
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
        except Exception:
            pass
        return []

    def _is_chat_model(self, model_name: str) -> bool:
        """判断模型是否是聊天模型"""
        model_lower = model_name.lower()
        # 排除嵌入模型
        if "embed" in model_lower or "nomic" in model_lower:
            return False
        # 检查是否是常见的聊天模型
        for prefix in self.CHAT_MODEL_PREFIXES:
            if prefix in model_lower:
                return True
        return False

    def _get_chat_model(self) -> str:
        """获取支持聊天的模型名称"""
        models = self._get_available_models()
        # 优先使用配置的模型
        config_model = settings.LLM_MODEL
        if config_model and config_model != "qwen2.5:7b":  # 默认值
            for m in models:
                if m.get("name") == config_model:
                    return config_model

        # 查找第一个支持聊天的模型
        for m in models:
            if self._is_chat_model(m.get("name", "")):
                return m.get("name")

        # 如果没有找到，返回配置的模型或默认值
        if models:
            return models[0].get("name", "qwen2.5:7b")
        return "qwen2.5:7b"

    def list_models(self) -> List[str]:
        """获取所有可用模型名称列表"""
        models = self._get_available_models()
        return [m.get("name", "") for m in models if m.get("name")]

    def list_chat_models(self) -> List[str]:
        """获取所有支持聊天的模型名称列表"""
        all_models = self.list_models()
        return [m for m in all_models if self._is_chat_model(m)]

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False
    ) -> Dict:
        """
        调用 LLM 进行对话

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            stream: 是否流式返回

        Returns:
            LLM 响应
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        return response.json()

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7
    ) -> str:
        """
        生成文本（支持流式和非流式响应）

        Args:
            prompt: 用户提示
            system: 系统提示
            temperature: 温度参数

        Returns:
            生成的文本
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
            "stream": False  # 不使用流式，等待完整响应
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        # 尝试解析 JSON
        try:
            result = response.json()
            # 兼容不同版本的 Ollama API
            return result.get("response", result.get("message", result.get("content", "")))
        except Exception:
            # 如果 JSON 解析失败，返回空字符串
            return ""

    def embed(self, text: str, model: str = None) -> List[float]:
        """
        生成文本嵌入

        Args:
            text: 输入文本
            model: 使用的模型名称（可选，默认使用配置的嵌入模型）

        Returns:
            嵌入向量
        """
        embed_model = model or settings.EMBEDDING_MODEL
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": embed_model,
            "prompt": text
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        return response.json().get("embedding", [])

    def check_availability(self) -> bool:
        """检查 LLM 服务是否可用"""
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# 全局实例
ollama_service = OllamaService()
