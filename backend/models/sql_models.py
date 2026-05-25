"""
SunChat Backend - Database Models (SQLAlchemy)
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from app.config import settings

# 创建基类
Base = declarative_base()

# 数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite only
)


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    avatar_url = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default={})


class ChatSession(Base):
    """聊天会话表"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(255))
    summary = Column(Text)
    is_pinned = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    raw_response = Column(Text)  # LLM 原始响应
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())


class Memory(Base):
    """记忆表"""
    __tablename__ = "memories"

    id = Column(String(100), primary_key=True)  # mem_uuid
    user_id = Column(Integer, nullable=False)
    type = Column(String(20), nullable=False)  # semantic, episodic, working
    category = Column(String(50))
    content = Column(Text, nullable=False)
    vector_id = Column(String(100))  # Chroma 中的向量 ID
    confidence = Column(Float, default=0.5)
    importance = Column(Integer, default=5)  # 1-10
    is_confirmed = Column(Boolean, default=True)
    extra_data = Column(JSON, default={})  # 改名：metadata -> extra_data
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    accessed_at = Column(DateTime, default=func.now())
    access_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class Emotion(Base):
    """情感记录表"""
    __tablename__ = "emotions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(String(100))
    user_id = Column(Integer, nullable=False)
    valence = Column(Float)  # -1 ~ 1
    arousal = Column(Float)  # 0 ~ 1
    dominant_emotion = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())


class KBFile(Base):
    """知识库文件表"""
    __tablename__ = "kb_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, md, txt
    file_size = Column(Integer, nullable=False)  # 字节数
    status = Column(String(20), default="uploading")  # uploading, processing, ready, failed
    error_message = Column(Text)
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    vector_ids = Column(JSON)  # 所有 chunk 的 vector_id
    extra_data = Column(JSON, default={})  # 改名：metadata -> extra_data
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)


class KBChunk(Base):
    """知识库分块表"""
    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    vector_id = Column(String(100), nullable=False)
    token_count = Column(Integer, default=0)
    extra_data = Column(JSON, default={})  # 改名：metadata -> extra_data
    created_at = Column(DateTime, default=func.now())


class SearchHistory(Base):
    """搜索历史表"""
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    query = Column(Text, nullable=False)
    intent = Column(String(50))  # general, academic, news, code
    results_count = Column(Integer, default=0)
    used_sources = Column(JSON)  # JSON 数组
    created_at = Column(DateTime, default=func.now())


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
