"""
SunChat Backend - Model Manager
模型管理唯一中心：动态解析、运行时切换、持久化、向量库一致性
"""
import os
import json
import time
import threading
from typing import List, Dict, Optional

import requests

from app.config import settings
from utils.logger import logger

# 常见聊天模型前缀（用于从 Ollama 模型列表中识别聊天模型）
CHAT_MODEL_PREFIXES = ["qwen", "llama", "glm", "deepseek", "mistral", "yi", "gemma", "phi", "codellama", "starcoder"]
# 常见嵌入模型名称/前缀
EMBED_MODEL_HINTS = ["embed", "nomic", "bge", "mxbai", "all-minilm", "e5", "snowflake", "gte", "text2vec"]
DEFAULT_CHAT_FALLBACK = "qwen2.5:7b"
DEFAULT_EMBED_FALLBACK = "nomic-embed-text"


class ModelManager:
    """
    模型管理器（全局单例）

    职责：
    - 动态解析当前聊天/嵌入模型（每次调用，带 TTL 缓存）
    - 运行时切换模型并持久化
    - 追踪向量库所用嵌入模型，保证一致性
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._available_cache: Optional[List[Dict]] = None
        self._available_ts: float = 0.0
        self._ttl = getattr(settings, "MODEL_CACHE_TTL", 30)
        # R-006: is_available 结果 TTL 缓存（含失败结果），/health 轮询不再每次挂 3s
        self._avail_flag: Optional[bool] = None
        self._avail_ts: float = 0.0
        self._avail_ttl = getattr(settings, "HEALTH_AVAIL_TTL", 30)
        # 运行时选择（持久化）
        self._chat_model_override: Optional[str] = None
        self._embedding_model_override: Optional[str] = None
        self._vector_store_model: Optional[str] = None
        self._load_config()

    @property
    def _config_path(self) -> str:
        # 运行时解析，支持测试隔离（模块级 import 早于配置 reload 时也不绑定生产路径）
        import app.config as _cfg
        return str(_cfg.settings.MODEL_CONFIG_PATH)

    # ==================== 持久化 ====================

    def _load_config(self):
        """从磁盘加载运行时模型选择（失败则降级为默认）"""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._chat_model_override = data.get("chat_model")
                self._embedding_model_override = data.get("embedding_model")
                self._vector_store_model = data.get("vector_store_model")
                logger.info(
                    f"[MODEL] 加载模型配置 - chat:{self._chat_model_override}, "
                    f"embedding:{self._embedding_model_override}, "
                    f"vector_store:{self._vector_store_model}"
                )
        except Exception as e:
            logger.error(f"[MODEL] 加载模型配置失败（使用默认） - 错误:{e}")

    def _save_config(self):
        """持久化运行时模型选择"""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            data = {
                "chat_model": self._chat_model_override,
                "embedding_model": self._embedding_model_override,
                "vector_store_model": self._vector_store_model,
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[MODEL] 模型配置已持久化 - {data}")
        except Exception as e:
            logger.error(f"[MODEL] 持久化模型配置失败 - 错误:{e}")

    # ==================== 可用模型（TTL 缓存） ====================

    def get_available_models(self, force_refresh: bool = False) -> List[Dict]:
        """获取 Ollama 可用模型列表（带 TTL 缓存）"""
        now = time.time()
        if (
            not force_refresh
            and self._available_cache is not None
            and (now - self._available_ts) < self._ttl
        ):
            return self._available_cache

        try:
            url = f"{settings.LLM_API_URL.rstrip('/')}/api/tags"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                with self._lock:
                    self._available_cache = models
                    self._available_ts = now
                logger.debug(f"[MODEL] 刷新可用模型列表 - 数量:{len(models)}")
                return models
        except Exception as e:
            logger.warning(f"[MODEL] 获取可用模型失败（返回缓存/空） - 错误:{e}")
            return self._available_cache or []

        return self._available_cache or []

    def is_available(self) -> bool:
        """Ollama 服务是否在线（R-006: 结果缓存 HEALTH_AVAIL_TTL 秒,与 R-003 探活缓存同语义）"""
        now = time.monotonic()
        if self._avail_flag is not None and (now - self._avail_ts) < self._avail_ttl:
            return self._avail_flag
        try:
            url = f"{settings.LLM_API_URL.rstrip('/')}/api/tags"
            resp = requests.get(url, timeout=3)
            val = resp.status_code == 200
        except Exception:
            val = False
        self._avail_flag = val
        self._avail_ts = now
        return val

    def invalidate_availability_cache(self) -> None:
        """模型切换/测试用:强制下次 is_available 实探。"""
        self._avail_flag = None
        self._avail_ts = 0.0

    # ==================== 模型分类 ====================

    @staticmethod
    def _is_chat_model(model_name: str) -> bool:
        lower = model_name.lower()
        if any(h in lower for h in EMBED_MODEL_HINTS):
            return False
        return any(p in lower for p in CHAT_MODEL_PREFIXES)

    @staticmethod
    def _is_embedding_model(model_name: str) -> bool:
        lower = model_name.lower()
        return any(h in lower for h in EMBED_MODEL_HINTS)

    def get_chat_models(self) -> List[str]:
        """可用的聊天模型"""
        return [
            m.get("name", "")
            for m in self.get_available_models()
            if m.get("name") and self._is_chat_model(m.get("name", ""))
        ]

    def get_embedding_models(self) -> List[str]:
        """可用的嵌入模型"""
        names = [
            m.get("name", "")
            for m in self.get_available_models()
            if m.get("name") and self._is_embedding_model(m.get("name", ""))
        ]
        return names or []

    def _model_exists(self, name: str) -> bool:
        return any(m.get("name") == name for m in self.get_available_models())

    # ==================== 动态解析 ====================

    def resolve_chat_model(self, requested: Optional[str] = None) -> str:
        """
        动态解析聊天模型

        优先级：请求指定 > 运行时切换值 > 配置值 > 自动探测 > 兜底
        每次调用都重新解析（配合 TTL 缓存），解决 Ollama 后启动问题
        """
        available = self.get_available_models()
        available_names = {m.get("name") for m in available if m.get("name")}

        # 1. 请求指定（若在线存在）
        if requested and requested in available_names:
            return requested
        # 2. 运行时切换值
        if self._chat_model_override and self._chat_model_override in available_names:
            return self._chat_model_override
        # 3. 配置值
        if settings.LLM_MODEL and settings.LLM_MODEL in available_names:
            return settings.LLM_MODEL
        # 4. 自动探测第一个聊天模型
        chat_models = self.get_chat_models()
        if chat_models:
            return chat_models[0]
        # 5. 兜底
        return requested or self._chat_model_override or settings.LLM_MODEL or DEFAULT_CHAT_FALLBACK

    def resolve_embedding_model(self, requested: Optional[str] = None) -> str:
        """动态解析嵌入模型"""
        available = self.get_available_models()
        available_names = {m.get("name") for m in available if m.get("name")}

        if requested and requested in available_names:
            return requested
        if self._embedding_model_override and self._embedding_model_override in available_names:
            return self._embedding_model_override
        if settings.EMBEDDING_MODEL and settings.EMBEDDING_MODEL in available_names:
            return settings.EMBEDDING_MODEL
        embed_models = self.get_embedding_models()
        if embed_models:
            return embed_models[0]
        return requested or self._embedding_model_override or settings.EMBEDDING_MODEL or DEFAULT_EMBED_FALLBACK

    # ==================== 运行时切换 ====================

    def set_chat_model(self, name: str) -> Dict:
        """切换聊天模型（校验存在）"""
        if not name:
            return {"success": False, "error": "模型名不能为空"}
        if not self._model_exists(name) and not self.is_available():
            # Ollama 不在线时允许切换（持久化），但标记为未验证
            logger.warning(f"[MODEL] Ollama 不在线，切换聊天模型为:{name}（未验证存在性）")
        elif not self._model_exists(name):
            return {"success": False, "error": f"模型不存在或不可用: {name}"}

        with self._lock:
            self._chat_model_override = name
            self._available_cache = None  # 强制刷新
            self.invalidate_availability_cache()  # R-006
        self._save_config()
        logger.info(f"[MODEL] 聊天模型已切换为: {name}")
        return {"success": True, "chat_model": name}

    def set_embedding_model(self, name: str) -> Dict:
        """
        切换嵌入模型

        返回 rebuild_required 标记：若与向量库所用模型不一致，需要重建向量库
        """
        if not name:
            return {"success": False, "error": "模型名不能为空"}
        if not self._model_exists(name) and not self.is_available():
            logger.warning(f"[MODEL] Ollama 不在线，切换嵌入模型为:{name}（未验证存在性）")
        elif not self._model_exists(name):
            return {"success": False, "error": f"模型不存在或不可用: {name}"}

        with self._lock:
            self._embedding_model_override = name
            self._available_cache = None
            self.invalidate_availability_cache()  # R-006
        self._save_config()
        logger.info(f"[MODEL] 嵌入模型已切换为: {name}")

        rebuild_required = (
            self._vector_store_model is not None and self._vector_store_model != name
        )
        return {
            "success": True,
            "embedding_model": name,
            "rebuild_required": rebuild_required,
            "warning": (
                f"嵌入模型已从 {self._vector_store_model} 切换为 {name}，"
                "现有向量维度可能不匹配，建议执行向量库重建以保证检索准确"
                if rebuild_required
                else None
            ),
        }

    def set_vector_store_model(self, name: str):
        """记录向量库当前使用的嵌入模型（重建后调用）"""
        with self._lock:
            self._vector_store_model = name
        self._save_config()

    # ==================== 状态 ====================

    def get_status(self) -> Dict:
        """获取完整模型状态（供 /models 接口）"""
        available = self.is_available()
        current_chat = self.resolve_chat_model()
        current_embed = self.resolve_embedding_model()

        # 向量库一致性
        if self._vector_store_model is None:
            vs_status = "unknown"  # 未记录（旧数据）
        elif self._vector_store_model == current_embed:
            vs_status = "ok"
        else:
            vs_status = "mismatch"

        return {
            "available": available,
            "api_url": settings.LLM_API_URL,
            "current": {
                "chat_model": current_chat,
                "embedding_model": current_embed,
            },
            "chat_models": self.get_chat_models(),
            "embedding_models": self.get_embedding_models(),
            "all_models": [m.get("name", "") for m in self.get_available_models() if m.get("name")],
            "overrides": {
                "chat_model": self._chat_model_override,
                "embedding_model": self._embedding_model_override,
            },
            "vector_store": {
                "model": self._vector_store_model,
                "status": vs_status,
                "rebuild_required": vs_status == "mismatch",
            },
        }


# 全局实例
model_manager = ModelManager()
