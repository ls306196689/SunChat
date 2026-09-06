"""
SunChat Backend - FTS Index (M2)
记忆关键词检索通道: SQLite FTS5(独立表) + 应用层中文分词(单字+二元组)。
采用独立表而非 external-content 模式: 索引存分词串与原文不同, 'delete' 命令
的旧内容校验会损坏 external-content 索引(调试记录 D-1);同步由应用层显式调用
(触发器无法执行 Python 分词)。
"""
import re
import sqlite3

from models.sql_models import get_engine
from utils.logger import logger

FTS_AVAILABLE: bool = True

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> str:
    """中文拆单字+相邻二元组, ASCII 词小写;空格连接成 FTS 文档。"""
    out = []
    for part in re.split(r"([A-Za-z0-9]+)", text or ""):
        if not part:
            continue
        if _TOKEN_RE.fullmatch(part):
            out.append(part.lower())
            continue
        chars = [ch for ch in part if "\u4e00" <= ch <= "\u9fff"]
        out.extend(chars)
        out.extend(a + b for a, b in zip(chars, chars[1:]))
    return " ".join(out)


def _escape_term(term: str) -> str:
    return term.replace('"', '""')


def init_fts() -> bool:
    """建 memory_fts(独立 FTS5 表)。旧版 external-content 表 → 自动 drop 重建。
    失败(无 FTS5 模块)→ 禁用, 返回 False。"""
    global FTS_AVAILABLE
    try:
        with get_engine().begin() as conn:
            cols = [r[0] for r in conn.exec_driver_sql(
                "SELECT name FROM pragma_table_info('memory_fts')"
            ).fetchall()]
            if cols and "memory_id" not in cols:
                conn.exec_driver_sql("DROP TABLE memory_fts")
                logger.info("[FTS] 检测到旧 external-content 表, 已重建")
            conn.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts "
                "USING fts5(memory_id UNINDEXED, tokens)"
            )
        FTS_AVAILABLE = True
        logger.info("[FTS] memory_fts 就绪")
        return True
    except sqlite3.OperationalError as e:
        FTS_AVAILABLE = False
        logger.warning(f"[FTS] FTS5 不可用, 关键词通道禁用(降级纯向量): {e}")
        return False


def fts_sync_upsert(memory_id: str, content: str) -> bool:
    """按 memory_id 重建其 FTS 行(先删后插)。所有记忆写路径在 SQLite 提交后调用。"""
    if not FTS_AVAILABLE:
        return False
    try:
        with get_engine().begin() as conn:
            conn.exec_driver_sql(
                "DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,)
            )
            conn.exec_driver_sql(
                "INSERT INTO memory_fts(memory_id, tokens) VALUES(?, ?)",
                (memory_id, tokenize(content)),
            )
        return True
    except sqlite3.OperationalError as e:
        # 表缺失(新库未走启动初始化): 补建后重试一次
        if "no such table" in str(e):
            if init_fts():
                return fts_sync_upsert(memory_id, content)
            return False
        logger.warning(f"[FTS] upsert 失败 - memory_id:{memory_id}: {e}")
        return False
    except Exception as e:
        logger.warning(f"[FTS] upsert 失败 - memory_id:{memory_id}: {e}")
        return False


def fts_sync_delete(memory_id: str) -> bool:
    if not FTS_AVAILABLE:
        return False
    try:
        with get_engine().begin() as conn:
            conn.exec_driver_sql(
                "DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,)
            )
        return True
    except Exception as e:
        logger.debug(f"[FTS] delete 跳过/失败 - memory_id:{memory_id}: {e}")
        return False


def fts_bootstrap_from_sqlite() -> int:
    """全量重建 FTS 索引(启动自愈),返回同步行数。失败 → 禁用通道。"""
    global FTS_AVAILABLE
    if not FTS_AVAILABLE:
        return 0
    try:
        with get_engine().begin() as conn:
            conn.exec_driver_sql("DELETE FROM memory_fts")
            rows = conn.exec_driver_sql(
                "SELECT id, content FROM memories WHERE is_active = 1"
            ).fetchall()
            for mid, content in rows:
                conn.exec_driver_sql(
                    "INSERT INTO memory_fts(memory_id, tokens) VALUES(?, ?)",
                    (mid, tokenize(content or "")),
                )
        logger.info(f"[FTS] bootstrap 完成 - 同步行数:{len(rows)}")
        return len(rows)
    except Exception as e:
        FTS_AVAILABLE = False
        logger.warning(f"[FTS] bootstrap 失败, 禁用关键词通道: {e}")
        return 0


def fts_search(query: str, user_id: int, n: int = 10) -> list:
    """返回 [(memory_id, score)] 按 bm25 优者先;不可用/无词返回 []。
    用户隔离/软删过滤靠 JOIN memories。"""
    if not FTS_AVAILABLE or not (query or "").strip():
        return []
    tokens = []
    seen = set()
    for t in tokenize(query).split():
        if t and t not in seen:
            seen.add(t)
            tokens.append(t)
    if not tokens:
        return []
    tokens = tokens[:16]  # 防超长查询
    match = " OR ".join(f'"{_escape_term(t)}"' for t in tokens)
    try:
        with get_engine().connect() as conn:
            rows = conn.exec_driver_sql(
                """
                SELECT f.memory_id, -bm25(memory_fts) AS s
                FROM memory_fts f
                JOIN memories m ON m.id = f.memory_id
                WHERE memory_fts MATCH ? AND m.user_id = ? AND m.is_active = 1
                ORDER BY bm25(memory_fts)
                LIMIT ?
                """,
                (match, user_id, n),
            ).fetchall()
        return [(r[0], float(r[1])) for r in rows]
    except Exception as e:
        logger.warning(f"[FTS] search 失败(返回空, 不影响向量通道) - query:'{query[:50]}': {e}")
        return []
