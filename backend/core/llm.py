"""
SunChat Backend - LLM Service (Ollama)
模型解析统一委托给 ModelManager（动态解析，支持运行时切换）
"""
import requests
import json
from typing import List, Dict, Optional, AsyncGenerator

from app.config import settings
from core.model_manager import model_manager
from utils.logger import logger


class OllamaService:
    """Ollama LLM 服务封装（模型动态解析）"""

    def __init__(self, api_url: str = None, model: str = None):
        self.api_url = api_url or settings.LLM_API_URL
        self.base_url = f"{self.api_url.rstrip('/')}"
        # 显式指定的模型（可选），否则每次动态解析
        self._fixed_model = model

    def _resolve_model(self, requested: Optional[str] = None) -> str:
        """解析本次调用使用的模型：显式参数 > 固定值 > 动态解析"""
        if requested:
            return requested
        if self._fixed_model:
            return self._fixed_model
        return model_manager.resolve_chat_model()

    def _resolve_embedding_model(self, requested: Optional[str] = None) -> str:
        return model_manager.resolve_embedding_model(requested)

    def list_models(self) -> List[str]:
        """获取所有可用模型名称列表"""
        return [m.get("name", "") for m in model_manager.get_available_models() if m.get("name")]

    def list_chat_models(self) -> List[str]:
        """获取所有支持聊天的模型名称列表"""
        return model_manager.get_chat_models()

    def list_embedding_models(self) -> List[str]:
        """获取所有嵌入模型名称列表"""
        return model_manager.get_embedding_models()

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None
    ) -> Dict:
        """
        调用 LLM 进行对话

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            stream: 是否流式返回
            model: 指定模型（可选，默认动态解析）
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self._resolve_model(model),
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
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None
    ):
        """
        生成文本（支持流式和非流式响应）

        Args:
            prompt: 用户提示
            system: 系统提示
            temperature: 温度参数
            stream: 是否流式
            model: 指定模型（可选，默认动态解析）

        Returns:
            生成的文本（非流式）或生成器（流式）
        """
        resolved_model = self._resolve_model(model)
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "stream": stream
        }

        if stream:
            def generate_stream():
                try:
                    response = requests.post(url, json=payload, stream=True)
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if data.get("done", False):
                                    break
                                content = data.get("message", {}).get("content", "")
                                yield content
                            except Exception:
                                continue
                except Exception as e:
                    yield f"\n[Error: {e}]"
            return generate_stream()
        else:
            try:
                response = requests.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                return result.get("message", {}).get("content", "")
            except Exception as e:
                logger.error(f"[LLM] generate 失败 (model={resolved_model}): {e}")
                return ""

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        生成文本嵌入

        Args:
            text: 输入文本
            model: 使用的模型名称（可选，默认动态解析）
        """
        resolved_model = self._resolve_embedding_model(model)
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": resolved_model,
            "prompt": text
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json().get("embedding", [])

    def check_availability(self) -> bool:
        """检查 LLM 服务是否可用"""
        return model_manager.is_available()


# 全局实例
ollama_service = OllamaService()
