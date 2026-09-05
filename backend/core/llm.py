"""
SunChat Backend - LLM Service (Ollama)

唯一的 Ollama HTTP 客户端：连接池 + 超时 + 模型动态解析（委托 ModelManager）。
core/embedding 与 core/agent/llm 复用此客户端，避免散落多处 requests.post。
"""
import json
from typing import List, Dict, Optional, Generator

import requests

from app.config import settings
from core.model_manager import model_manager
from utils.logger import logger

# 全局 HTTP 会话（连接池复用 + 默认超时），所有 Ollama 调用走这里
_http = requests.Session()
_http.headers.update({"Content-Type": "application/json"})


def _post(url: str, payload: dict, timeout: Optional[int] = None, stream: bool = False):
    return _http.post(url, json=payload, timeout=timeout or settings.LLM_TIMEOUT, stream=stream)


class OllamaService:
    """Ollama LLM 服务封装（模型动态解析，支持流式与错误控制）"""

    def __init__(self, api_url: str = None, model: str = None):
        self.api_url = api_url or settings.LLM_API_URL
        self.base_url = f"{self.api_url.rstrip('/')}"
        self._fixed_model = model

    def _resolve_model(self, requested: Optional[str] = None) -> str:
        if requested:
            return requested
        if self._fixed_model:
            return self._fixed_model
        return model_manager.resolve_chat_model()

    def _resolve_embedding_model(self, requested: Optional[str] = None) -> str:
        return model_manager.resolve_embedding_model(requested)

    # ---------- 模型列表 ----------
    def list_models(self) -> List[str]:
        return [m.get("name", "") for m in model_manager.get_available_models() if m.get("name")]

    def list_chat_models(self) -> List[str]:
        return model_manager.get_chat_models()

    def list_embedding_models(self) -> List[str]:
        return model_manager.get_embedding_models()

    # ---------- 对话 ----------
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> Dict:
        """调用 LLM 对话，返回完整响应 dict（含 eval_count 等用量信息）。"""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self._resolve_model(model),
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        resp = _post(url, payload)
        resp.raise_for_status()
        return resp.json()

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None,
        raise_on_error: bool = False,
    ):
        """
        生成文本。

        Args:
            raise_on_error: True 时失败抛异常（供需要明确错误的调用方）；
                            False 时失败返回 ""（保持既有兼容）。
        Returns:
            非流式：str；流式：同步 generator。
        """
        resolved_model = self._resolve_model(model)
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "stream": stream,
        }

        if stream:
            def generate_stream() -> Generator[str, None, None]:
                try:
                    resp = _post(url, payload, stream=True)
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if data.get("done", False):
                                    break
                                yield data.get("message", {}).get("content", "")
                            except Exception:
                                continue
                except Exception as e:
                    logger.error(f"[LLM] 流式生成失败 (model={resolved_model}): {e}")
                    if raise_on_error:
                        raise
                    yield f"\n[Error: {e}]"
            return generate_stream()

        try:
            resp = _post(url, payload)
            resp.raise_for_status()
            result = resp.json()
            return result.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"[LLM] generate 失败 (model={resolved_model}): {e}")
            if raise_on_error:
                raise
            return ""

    def generate_detailed(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        model: Optional[str] = None,
        raise_on_error: bool = True,
    ) -> Dict:
        """非流式生成，返回 {content, tokens_used, prompt_tokens}（真实 Ollama 用量）。"""
        resolved_model = self._resolve_model(model)
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "stream": False,
        }
        try:
            resp = _post(url, payload)
            resp.raise_for_status()
            result = resp.json()
            content = result.get("message", {}).get("content", "")
            return {
                "content": content,
                "tokens_used": result.get("eval_count", 0),
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "model": result.get("model", resolved_model),
            }
        except Exception as e:
            logger.error(f"[LLM] generate_detailed 失败 (model={resolved_model}): {e}")
            if raise_on_error:
                raise
            return {"content": "", "tokens_used": 0, "prompt_tokens": 0, "model": resolved_model}

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """生成单条文本嵌入（委托 embedding_service 以复用批量逻辑）。"""
        from core.embedding import embedding_service
        return embedding_service.embed(text, model=model)

    def check_availability(self) -> bool:
        return model_manager.is_available()


# 全局实例
ollama_service = OllamaService()
