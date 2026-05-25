"""
SunChat Backend - Configuration Management
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # Ollama 配置
    LLM_API_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b"

    # 嵌入模型配置
    EMBEDDING_API_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./data/sunchat.db"
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # 搜索配置
    SEARCH_DUCKDUCKGO_API: str = ""  # 可选，留空使用无 Key 版本

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return Settings()


settings = get_settings()
