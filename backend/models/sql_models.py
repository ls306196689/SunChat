"""
SunChat Backend - Database Models (SQLAlchemy)
"""
import threading
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from app.config import settings

# 创建基类
Base = declarative_base()

# ==================== 惰性 Engine / Session 工厂 ====================
# 不在 import 时创建 engine：否则 pytest 收集阶段 import 本模块会用“当时的”配置
# （生产库）绑定 engine，测试 fixture 之后才改配置就来不及了。
# 惰性创建 + URL/inode 变更自动重建，保证测试 reload 配置、删库重建后能正确指向新库。
_engine = None
_engine_url = None
_engine_file_inode = None
_session_local = None


def _guard_pytest_real_db(url: str):
    """守卫：pytest 运行期间禁止连接生产库（真实记忆数据），防止测试隔离失误清库。"""
    import os as _os
    if _os.environ.get("PYTEST_CURRENT_TEST"):
        expect = str(url)
        if expect.startswith("sqlite:///") and "test_" not in expect:
            raise RuntimeError(
                f"TEST ISOLATION GUARD: pytest 运行中测试代码尝试连接生产数据库 {expect}。"
                "请在测试模块内 patch 环境变量 DATABASE_URL 指向 ./data/test_*.db"
            )


def _make_engine(url: str):
    _guard_pytest_real_db(url)
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def _sqlite_file(url: str):
    """从 sqlite URL 提取文件路径（内存库/非 sqlite 返回 None）。"""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        return url[len("sqlite:///"):]
    return None


def _file_inode(path):
    import os
    try:
        return os.stat(path).st_ino
    except (FileNotFoundError, OSError):
        return None


def _reset_engine_state():
    global _engine, _engine_url, _engine_file_inode, _session_local
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _engine_url = None
    _engine_file_inode = None
    _session_local = None
    reset_thread_session()


def get_engine():
    """获取数据库引擎（惰性；URL 或 SQLite 文件 inode 变更时自动重建）。

    追踪 SQLite 文件 inode：测试删库重建后 inode 变化，自动 dispose 旧 engine
    （其连接仍指向被删旧文件），重建指向新文件。
    """
    global _engine, _engine_url, _engine_file_inode, _session_local
    import app.config as _cfg  # 运行时读取，反映 reload 后的最新配置
    url = str(_cfg.settings.DATABASE_URL)

    fpath = _sqlite_file(url)
    cur_inode = _file_inode(fpath) if fpath else None

    def _rebuild():
        global _engine, _engine_url, _engine_file_inode, _session_local
        if _engine is not None:
            try:
                _engine.dispose()
            except Exception:
                pass
        _engine = _make_engine(url)
        _engine_url = url
        _engine_file_inode = _file_inode(fpath) if fpath else None
        _session_local = None
        reset_thread_session()

    if _engine is None or _engine_url != url:
        # 新 engine（或配置 URL 变更）
        if _engine is not None:
            try:
                _engine.dispose()
            except Exception:
                pass
        _engine = _make_engine(url)
        _engine_url = url
        _engine_file_inode = cur_inode  # 文件尚不存在则 None，待首次连接后确认
        _session_local = None
    else:
        # 同 URL：判断 SQLite 文件是否被删/重建
        if _engine_file_inode is None:
            # 创建时文件不存在（未确认）；文件出现后确认其 inode（首次连接建库），不重置
            if cur_inode is not None:
                _engine_file_inode = cur_inode
        elif cur_inode is None:
            # 文件被删除 -> 重置（新文件将由下次连接创建）
            _rebuild()
        elif cur_inode != _engine_file_inode:
            # 文件被重建（inode 变化）-> 重置
            _rebuild()
    return _engine


def get_session_local():
    """获取 Session 工厂（惰性，绑定当前 engine）。"""
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _session_local


def reset_engine():
    """销毁当前 engine / Session 工厂并清理线程 Session。

    用于测试重建 DB 文件之后：旧 engine 的连接仍指向被删的旧文件
    （SQLite 靠打开句柄续命旧文件），必须 dispose 后重建才能指向新文件。
    """
    global _engine, _engine_url, _session_local
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _engine_url = None
    _session_local = None
    reset_thread_session()


# 线程本地存储：每个线程池 worker 持有一个独立 Session，
# 既保证并发线程间互不共享（线程安全），又让同一线程内多次访问复用同一 Session。
_thread_local = threading.local()


def get_thread_session():
    """获取当前线程的 Session（不存在则新建）。

    设计说明：
    - 路由改为同步 ``def`` 后由 FastAPI 丢进线程池执行，每线程一个 Session 天然隔离。
    - service 仍以 ``self.db`` 属性暴露（返回本线程 Session），保持既有调用/测试兼容。
    - 后台任务（BackgroundTasks）运行在独立线程，自动获得独立 Session。
    - engine 轮转（测试逐模块换库 / 生产 URL 或 inode 变化）后，线程本地旧 Session
      仍绑在被 dispose/删除的旧 Engine 上 → "unable to open database file"；
      此处按 bind 的 Engine 身份检测并重建 Session。
    """
    session = getattr(_thread_local, "session", None)
    engine = get_engine()
    if session is None:
        session = get_session_local()()
        session._bound_engine = engine
        _thread_local.session = session
    elif getattr(session, "_bound_engine", None) is not engine:
        try:
            if session.in_transaction():
                session.rollback()
            session.close()
        finally:
            session = get_session_local()()
            session._bound_engine = engine
            _thread_local.session = session
    # 注意：此处不能回滚 in_transaction 的事务——同一方法内多次访问 self.db
    # （add → commit → refresh）期间存在合法待提交事务，回滚会毁掉未提交的写入。
    # 遗留的只读事务留着无害（后续操作可继续或提交），异常清理由调用方/边界负责。
    return session


def reset_thread_session():
    """关闭并释放当前线程的 Session（用于测试/worker 生命周期边界）。"""
    session = getattr(_thread_local, "session", None)
    if session is not None:
        try:
            if session.in_transaction():
                session.rollback()
            session.close()
        finally:
            _thread_local.session = None


class DBSessionMixin:
    """为 service 提供线程安全的 ``db`` 属性。

    - 默认返回当前线程的 Session（线程池 worker 间隔离，线程内复用）。
    - 支持 ``service.db = session`` 覆盖赋值（保留原 API 契约，供测试注入）。
    """

    _db_override = None

    @property
    def db(self):
        if self._db_override is not None:
            return self._db_override
        return get_thread_session()

    @db.setter
    def db(self, value):
        self._db_override = value


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
    storage_path = Column(String(500))  # 落盘绝对路径（上传管道用）
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


def ensure_schema():
    """建表 + 对旧库补齐缺失列/数据（轻量迁移，不依赖 alembic）。

    ``create_all`` 只建不存在的表，不会给已有表加列；模型新增列后需在此迁移。
    """
    Base.metadata.create_all(bind=get_engine())
    from sqlalchemy import inspect, text
    eng = get_engine()
    insp = inspect(eng)
    tables = set(insp.get_table_names())

    # kb_files.storage_path（上传管道落盘路径）
    if "kb_files" in tables:
        cols = {c["name"] for c in insp.get_columns("kb_files")}
        if "storage_path" not in cols:
            with eng.begin() as conn:
                conn.execute(text("ALTER TABLE kb_files ADD COLUMN storage_path VARCHAR(500)"))

    # 记忆分类拼写统一：habbit -> habit（幂等，无匹配则为 no-op）
    if "memories" in tables:
        with eng.begin() as conn:
            conn.execute(text("UPDATE memories SET category = 'habit' WHERE category = 'habbit'"))


def init_db():
    """初始化数据库（建表 + 轻量迁移 + FTS 影子表）。"""
    ensure_schema()
    try:
        from core.fts_index import init_fts
        init_fts()
    except Exception:
        pass  # FTS5 不可用时静默降级, 不影响建表


def get_db():
    """获取数据库会话（生成器，供 FastAPI Depends 使用）"""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
