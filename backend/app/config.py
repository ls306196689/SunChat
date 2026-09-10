"""
SunChat Backend - Configuration Management
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# 项目根目录（backend/）：基于本文件定位，消除对 CWD 的依赖
BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"


class Settings(BaseSettings):
    """应用配置"""

    # Ollama 配置
    LLM_API_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b"
    LLM_TIMEOUT: int = 300  # LLM 请求超时（秒），本地生成较慢
    LLM_LIGHT_TIMEOUT: int = 20  # R-006: 路由/提取等轻量 LLM 调用短超时,失败快速回退
    HEALTH_AVAIL_TTL: int = 30  # R-006: /health LLM 探活结果缓存秒数（同 R-003 DDG 模式）

    # 嵌入模型配置（bge-m3: 中文语义优于 nomic-embed-text, 决策 D-001;切换后需重建向量库）
    EMBEDDING_API_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "bge-m3"

    # 模型管理配置
    MODEL_CONFIG_PATH: str = str(DATA_DIR / "model_config.json")  # 运行时模型选择持久化（绝对路径）
    MODEL_CACHE_TTL: int = 30  # 可用模型列表缓存秒数

    # 数据库配置（绝对路径，消除 CWD 依赖）
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'sunchat.db'}"
    CHROMA_PERSIST_DIR: str = str(DATA_DIR / "chroma")
    UPLOAD_DIR: str = str(UPLOAD_DIR)  # 知识库上传落盘目录

    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # 单用户本地模式：统一用户标识（全项目引用，避免散落硬编码 user_id=1）
    LOCAL_USER_ID: int = 1

    # CORS 白名单（逗号分隔）；本地优先，默认只放行本地前端端口
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    # 上传约束
    ALLOWED_FILE_TYPES: str = "pdf,docx,txt,md"
    MAX_UPLOAD_MB: int = 20

    # 搜索配置
    SEARCH_DUCKDUCKGO_API: str = ""  # 可选，留空使用无 Key 版本
    SEARCH_TIMEOUT: int = 10  # 搜索超时（秒）

    # 对话流程配置
    CHAT_HISTORY_MESSAGES: int = 6   # 多轮上下文携带的最近消息条数
    MEMORY_ROUTER_LLM_FALLBACK: bool = True  # 规则未命中且输入较长时才用 LLM 兜底分析
    MEMORY_ROUTER_LLM_MIN_LEN: int = 12  # 低于此长度的输入直接信任规则（问候语等 0 LLM）

    # 记忆写入阈值（宁缺毋滥, 决策 D-004）
    MEMORY_WRITE_MIN_CONFIDENCE: float = 0.6
    MEMORY_WRITE_MIN_IMPORTANCE: int = 4

    # 存储一致性
    RECONCILE_ON_STARTUP: bool = True  # 启动时 SQLite↔Chroma 对账自愈

    # 混合检索 / 排序融合（权重 α,β,γ,δ = 相似度,重要性,时间衰减,访问反馈）
    MEMORY_VEC_TOPN: int = 10            # 向量通道召回数
    MEMORY_FTS_TOPN: int = 10            # 关键词通道召回数
    MEMORY_SIM_THRESHOLD: float = 0.3    # 注入前最低余弦相似度（保守起步, 评测定参）
    MEMORY_FINAL_MIN_SCORE: float = 0.15
    MEMORY_RANK_WEIGHTS: str = "0.7,0.15,0.1,0.05"
    MEMORY_ACCESS_FEEDBACK: bool = True  # 命中注入后更新 access_count/accessed_at
    MEMORY_INJECT_TOPK: int = 5          # 注入 system prompt 的记忆条数

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return Settings()


settings = get_settings()
