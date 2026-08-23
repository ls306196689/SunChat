"""
SunChat Backend - Embedding Service
嵌入模型动态解析，委托给 ModelManager（支持运行时切换）
"""
from typing import List
from app.config import settings
from core.model_manager import model_manager
from utils.logger import logger


class EmbeddingService:
    """嵌入模型服务（使用 Ollama，模型动态解析）"""

    def __init__(self, api_url: str = None, model: str = None):
        self.api_url = api_url or settings.EMBEDDING_API_URL
        self.base_url = f"{self.api_url.rstrip('/')}"
        # 显式指定的模型（可选），否则每次动态解析
        self._fixed_model = model

    def _resolve_model(self, requested: str = None) -> str:
        if requested:
            return requested
        if self._fixed_model:
            return self._fixed_model
        return model_manager.resolve_embedding_model()

    def list_models(self) -> List[str]:
        """获取所有可用模型名称列表"""
        return [m.get("name", "") for m in model_manager.get_available_models() if m.get("name")]

    def embed(self, text: str, model: str = None) -> List[float]:
        """
        生成文本嵌入

        Args:
            text: 输入文本
            model: 使用的模型名称（可选，默认动态解析）
        """
        resolved_model = self._resolve_model(model)
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": resolved_model,
            "prompt": text
        }

        try:
            import requests
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            logger.error(f"[EMBED] embed 失败 (model={resolved_model}): {e}")
            raise

    def embed_batch(self, texts: List[str], model: str = None) -> List[List[float]]:
        """批量生成嵌入"""
        return [self.embed(text, model) for text in texts]


# 全局实例
embedding_service = EmbeddingService()
