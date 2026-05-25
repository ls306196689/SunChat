"""
SunChat Backend - Pydantic Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# 通用响应
class Response(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


# 用户相关
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: Optional[str] = None
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: Optional[str] = None
    token: Optional[str] = None


# 聊天相关
class MessageCreate(BaseModel):
    session_id: str
    content: str
    memory_context: bool = True
    search_enabled: bool = True
    model: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ChatSessionCreate(BaseModel):
    title: Optional[str] = None
    initial_message: Optional[str] = None


class ChatSessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: datetime


# 记忆相关
class MemoryCreate(BaseModel):
    content: str
    type: str = "semantic"
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: int = 5


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    confidence: Optional[float] = None
    importance: Optional[int] = None
    is_confirmed: Optional[bool] = None


class MemoryResponse(BaseModel):
    id: str
    type: str
    category: Optional[str] = None
    content: str
    confidence: float
    importance: int
    tags: List[str]
    created_at: datetime


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None


class MemorySearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]


# 搜索相关
class SearchRequest(BaseModel):
    query: str
    intent: Optional[str] = None
    sources: Optional[List[str]] = None
    use_memory_context: bool = True


class SearchResult(BaseModel):
    title: str
    url: str
    source: str
    snippet: str
    score: float
    metadata: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    query: str
    intent: str
    results: List[SearchResult]
    used_memory: Optional[List[Dict[str, Any]]] = None


# 知识库相关
class KBFileUpload(BaseModel):
    file_id: int
    filename: str
    status: str


class KBFileResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    created_at: datetime


class KBQuestionRequest(BaseModel):
    file_ids: List[int]
    query: str


class KBQuestionResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
