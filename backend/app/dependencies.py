"""
SunChat Backend - Dependencies
"""
from typing import Generator
from app.config import settings


def get_llm_api_url() -> str:
    """获取 LLM API 地址"""
    return settings.LLM_API_URL


def get_llm_model() -> str:
    """获取 LLM 模型名称"""
    return settings.LLM_MODEL


def get_embedding_model() -> str:
    """获取嵌入模型名称"""
    return settings.EMBEDDING_MODEL


def get_chroma_persist_dir() -> str:
    """获取 Chroma 持久化目录"""
    return settings.CHROMA_PERSIST_DIR
