"""
SunChat Backend - Embedding Service
嵌入模型动态解析（委托 ModelManager），复用 core/llm 的共享 HTTP 会话。
"""
from typing import List, Optional

from app.config import settings
from core.model_manager import model_manager
from core.llm import _http  # 共享连接池（统一客户端）
from utils.logger import logger


class EmbeddingService:
    """嵌入模型服务（使用 Ollama，模型动态解析）"""

    def __init__(self, api_url: str = None, model: str = None):
        self.api_url = api_url or settings.EMBEDDING_API_URL
        self.base_url = self.api_url.rstrip("/")
        self._fixed_model = model

    def _resolve_model(self, requested: Optional[str] = None) -> str:
        if requested:
            return requested
        if self._fixed_model:
            return self._fixed_model
        return model_manager.resolve_embedding_model()

    def list_models(self) -> List[str]:
        return [m.get("name", "") for m in model_manager.get_available_models() if m.get("name")]

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """生成单条文本嵌入（失败抛异常，由调用方决定降级）。"""
        resolved_model = self._resolve_model(model)
        url = f"{self.base_url}/api/embeddings"
        try:
            resp = _http.post(
                url,
                json={"model": resolved_model, "prompt": text},
                timeout=settings.LLM_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])
        except Exception as e:
            logger.error(f"[EMBED] embed 失败 (model={resolved_model}): {e}")
            raise

    def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """批量生成嵌入。

        优先使用 Ollama `/api/embed` 复数接口（一次请求全部文本，结果与输入同序）；
        接口不可用（旧版 Ollama 404/异常）时回退逐条 `/api/embeddings`。
        """
        if not texts:
            return []
        resolved_model = self._resolve_model(model)
        url = f"{self.base_url}/api/embed"
        try:
            resp = _http.post(
                url,
                json={"model": resolved_model, "input": texts},
                timeout=settings.LLM_TIMEOUT,
            )
            resp.raise_for_status()
            embs = resp.json().get("embeddings")
            if embs is not None and len(embs) == len(texts) and all(e for e in embs):
                return embs
            logger.warning(f"[EMBED] 批量嵌入返回异常（数量/空值不符），回退逐条")
        except Exception as e:
            logger.warning(f"[EMBED] 批量嵌入失败，回退逐条: {e}")
        return [self.embed(t, model) for t in texts]


# 全局实例
embedding_service = EmbeddingService()
