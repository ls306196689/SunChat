"""
SunChat Backend - Embedding Service
"""
from typing import List
from app.config import settings


class EmbeddingService:
    """嵌入模型服务（使用 Ollama）"""

    def __init__(self, api_url: str = None, model: str = None):
        self.api_url = api_url or settings.EMBEDDING_API_URL
        self.base_url = f"{self.api_url.rstrip('/')}"
        # 动态获取本地运行的嵌入模型
        self.model = model or self._get_first_embedding_model()

    def _get_available_models(self) -> List[str]:
        """获取 Ollama 本地运行的模型列表"""
        try:
            url = f"{self.base_url}/api/tags"
            response = __import__('requests').get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    def _get_first_embedding_model(self) -> str:
        """获取第一个可用的嵌入模型"""
        # 优先使用配置的嵌入模型
        if settings.EMBEDDING_MODEL:
            return settings.EMBEDDING_MODEL
        # 尝试常见的嵌入模型
        common_embedding_models = [
            "nomic-embed-text",
            "bge-small-zh",
            "mxbai-embed-large",
            "all-minilm"
        ]
        available = self._get_available_models()
        for model in common_embedding_models:
            if model in available:
                return model
        # 如果没有找到，返回第一个可用模型
        if available:
            return available[0]
        return "nomic-embed-text"

    def list_models(self) -> List[str]:
        """获取所有可用模型名称列表"""
        return self._get_available_models()

    def embed(self, text: str, model: str = None) -> List[float]:
        """
        生成文本嵌入

        Args:
            text: 输入文本
            model: 使用的模型名称（可选）

        Returns:
            嵌入向量
        """
        embed_model = model or self.model
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": embed_model,
            "prompt": text
        }

        response = __import__('requests').post(url, json=payload)
        response.raise_for_status()

        return response.json().get("embedding", [])

    def embed_batch(self, texts: List[str], model: str = None) -> List[List[float]]:
        """
        批量生成嵌入

        Args:
            texts: 输入文本列表
            model: 使用的模型名称（可选）

        Returns:
            嵌入向量列表
        """
        return [self.embed(text, model) for text in texts]


embedding_service = EmbeddingService()
