"""
SunChat Backend - Logger Utility
提供统一的日志记录功能
R-013: 请求级 trace 关联 + 环节事件(evt) + 高频降噪(阈值聚合)
"""
import contextvars
import logging
import os
import re
import time
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

# 创建日志目录
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
LOG_FILE = os.path.join(LOG_DIR, f"sunchat_{datetime.now().strftime('%Y%m%d')}.log")
LOG_MAX_BYTES = 10 * 1024 * 1024  # 单文件 10MB
LOG_BACKUP_COUNT = 7               # 滚动保留 7 份
LOG_RETENTION_DAYS = 30            # 历史日志保留 30 天

# 配置日志格式（R-013: 新增 trace 列 %(trace)s → [r=xxxxxx]）
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(trace)s | %(name)s | %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 聚合降噪阈值：同模板 WARNING+ 每满 N 条放出一条重复摘要（首条必放行）
AGG_THRESHOLD = 20

# ==================== R-013: trace 上下文 ====================
_trace_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace", default="-")


def new_trace() -> str:
    """生成 6 位短 trace 码。"""
    return uuid.uuid4().hex[:6]


def set_trace(value: str):
    """设置当前上下文 trace,返回 token(供 reset)。"""
    return _trace_var.set(value or "-")


def reset_trace(token) -> None:
    try:
        _trace_var.reset(token)
    except (ValueError, LookupError):
        pass


def get_trace() -> str:
    return _trace_var.get()


class TraceFilter(logging.Filter):
    """为每条 record 注入 trace 字段(取当前上下文)。"""

    def filter(self, record):
        if not hasattr(record, "trace"):
            record.trace = f"[r={_trace_var.get()}]"
        return True


_DIGITS = re.compile(r"\d+")


class AggregatingFilter(logging.Filter):
    """高频降噪：同模板 WARNING+ 抑制,首条必放行,每满 threshold 放出一条重复摘要。

    - evt= 事件行(record.no_agg=True)永不聚合(保证"成功失败都有记录"底线)。
    - 模板 = 级别 + 数字掩码后的消息前缀,使 attempt1/2/3、count 变化归并。
    - 计数达 threshold 整数倍 → 放行 `[repeat×N]` 摘要,持续可见但不刷屏。
    """

    def __init__(self, threshold: int = AGG_THRESHOLD):
        super().__init__()
        self.threshold = max(2, int(threshold))
        self._counts = {}

    def _key(self, record) -> str:
        msg = record.getMessage()
        return f"{record.levelno}|{_DIGITS.sub('#', msg)[:72]}"

    def filter(self, record):
        if record.levelno < logging.WARNING:
            return True
        if getattr(record, "no_agg", False):
            return True
        key = self._key(record)
        self._counts[key] = self._counts.get(key, 0) + 1
        c = self._counts[key]
        if c == 1:
            return True  # 首见必全量放行
        if c % self.threshold == 0:
            record.msg = f"{record.getMessage()}  [repeat×{c}]"
            record.args = None
            return True
        return False

    def reset(self):
        self._counts.clear()



def _cleanup_old_logs():
    """删除超过 LOG_RETENTION_DAYS 的历史日志(含滚动备份)。失败静默。"""
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    try:
        for fn in os.listdir(LOG_DIR):
            if not fn.startswith("sunchat_"):
                continue
            fp = os.path.join(LOG_DIR, fn)
            try:
                if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
                    os.remove(fp)
            except OSError:
                pass
    except OSError:
        pass


# 聚合/trace 过滤器共享实例(按 handler 挂载,状态进程级)
_agg_filter = AggregatingFilter()
_trace_filter = TraceFilter()


def get_logger(name: str = 'sunchat') -> logging.Logger:
    """获取配置好的日志器"""
    logger = logging.getLogger(name)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 文件处理器(R-004: 轮转封顶,单文件 10MB × 7 份;跨日仍按日新文件)
    _cleanup_old_logs()
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    file_handler.addFilter(_trace_filter)   # R-013: 注入 trace
    file_handler.addFilter(_agg_filter)     # R-013: 高频降噪
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    console_handler.addFilter(_trace_filter)
    console_handler.addFilter(_agg_filter)
    logger.addHandler(console_handler)

    return logger


# ==================== R-013: 环节事件 ====================

def log_event(log: logging.Logger, domain: str, action: str, result: str,
              exc: bool = False, **fields) -> None:
    """环节事件行:`evt=<domain>.<action> result=<ok|fail|skip> k=v …`

    关键环节统一入口——成功失败皆记(验收基线);fail 建议 exc=True 带堆栈。
    以 extra(no_agg) 豁免降噪,字段做竖线/换行净化防日志注入。
    """
    parts = [f"evt={domain}.{action}", f"result={result}"]
    for k, v in fields.items():
        s = str(v)
        if len(s) > 120:
            s = s[:117] + "..."
        parts.append(f"{k}={s.replace('|', '/').replace(chr(10), ' ')}")
    level = logging.ERROR if result == "fail" else logging.INFO
    log.log(level, " ".join(parts), exc_info=exc,
            extra={"no_agg": True, "trace": f"[r={get_trace()}]"})


# ==================== R-013: uvicorn 接入治理 ====================

def setup_uvicorn_logging() -> None:
    """uvicorn.access 由自有请求摘要中间件替代(R-013/D-703);error 流保留。

    第三方库降噪:httpx/httpcore/urllib3/chromadb/numexpr INFO→WARNING。
    幂等。"""
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    for noisy in ("httpx", "httpcore", "urllib3", "chromadb", "numexpr",
                  "sentence_transformers", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(
            max(logging.WARNING, logging.getLogger(noisy).level))




# 全局日志器实例
logger = get_logger()


class TestLogger:
    """测试日志记录器 - 记录测试过程"""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.test_start_time = datetime.now()
        self.test_results = {
            'test_name': test_name,
            'start_time': self.test_start_time.isoformat(),
            'steps': [],
            'passed': False,
            'end_time': None,
            'duration': None
        }
        self.logger = logger

    def log_step(self, step_name: str, status: str, details: str = ""):
        """记录测试步骤"""
        timestamp = datetime.now().isoformat()
        step = {
            'timestamp': timestamp,
            'step_name': step_name,
            'status': status,  # 'pending', 'running', 'passed', 'failed'
            'details': details
        }
        self.test_results['steps'].append(step)

        level = logging.INFO
        if status == 'failed':
            level = logging.ERROR
        elif status == 'passed':
            level = logging.INFO

        self.logger.log(level, f"[TEST:{self.test_name}] {step_name} - {status}")
        if details:
            self.logger.debug(f"[TEST:{self.test_name}]  详情: {details}")

    def mark_passed(self):
        """标记测试通过"""
        self.test_results['passed'] = True
        self.test_results['end_time'] = datetime.now().isoformat()
        self.test_results['duration'] = (datetime.now() - self.test_start_time).total_seconds()
        self.logger.info(f"[TEST:{self.test_name}] 测试通过 - 用时 {self.test_results['duration']:.2f}秒")

    def mark_failed(self, error: str = ""):
        """标记测试失败"""
        self.test_results['passed'] = False
        self.test_results['end_time'] = datetime.now().isoformat()
        self.test_results['duration'] = (datetime.now() - self.test_start_time).total_seconds()
        self.logger.error(f"[TEST:{self.test_name}] 测试失败 - {error}")
        if error:
            self.logger.error(f"[TEST:{self.test_name}] 错误: {error}")

    def get_results(self) -> dict:
        """获取测试结果"""
        return self.test_results


class MemoryLogger:
    """记忆操作日志记录器"""

    def __init__(self):
        self.logger = logger

    def log_memory_create(self, user_id: int, content: str, memory_type: str, category: str, success: bool):
        """记录记忆创建"""
        status = "成功" if success else "失败"
        self.logger.info(f"[MEMORY] 创建记忆 - 用户:{user_id}, 类型:{memory_type}, 分类:{category}, 内容:{content[:50]}..., 状态:{status}")

    def log_memory_search(self, user_id: int, query: str, results_count: int, success: bool):
        """记录记忆搜索"""
        status = "成功" if success else "失败"
        self.logger.info(f"[MEMORY] 搜索记忆 - 用户:{user_id}, 查询:{query}, 结果数:{results_count}, 状态:{status}")

    def log_memory_extract(self, user_message: str, ai_response: str, memories_count: int, success: bool):
        """记录记忆提取"""
        status = "成功" if success else "失败"
        self.logger.info(f"[MEMORY] 提取记忆 - 用户消息:{user_message[:50]}..., AI响应:{ai_response[:50]}..., 提取数:{memories_count}, 状态:{status}")


class ChatLogger:
    """聊天操作日志记录器"""

    def __init__(self):
        self.logger = logger

    def log_message_send(self, user_id: int, session_id: int, content: str):
        """记录消息发送"""
        self.logger.info(f"[CHAT] 用户消息 - 用户:{user_id}, 会话:{session_id}, 内容:{content[:100]}...")

    def log_memory_context(self, user_id: int, context_count: int, memories: list):
        """记录记忆上下文构建"""
        self.logger.info(f"[CHAT] 记忆上下文 - 用户:{user_id}, 上下文数:{context_count}")
        for i, m in enumerate(memories[:3]):  # 只记录前3条
            self.logger.debug(f"[CHAT]   记忆{i+1}: {m.get('content', '')[:50]}... (相似度: {m.get('similarity', 0):.2f})")

    def log_ai_response(self, user_id: int, session_id: int, response_length: int, memory_updates: int):
        """记录AI响应"""
        self.logger.info(f"[CHAT] AI响应 - 用户:{user_id}, 会话:{session_id}, 响应长度:{response_length}, 新记忆:{memory_updates}")


class KnowledgeLogger:
    """知识库操作日志记录器"""

    def __init__(self):
        self.logger = logger

    def log_file_upload(self, file_id: int, filename: str, file_type: str, file_size: int):
        """记录文件上传"""
        self.logger.info(f"[KNOWLEDGE] 上传文件 - 文件ID:{file_id}, 文件名:{filename}, 类型:{file_type}, 大小:{file_size}字节")

    def log_file_process(self, file_id: int, status: str, chunk_count: int = 0, error: str = ""):
        """记录文件处理"""
        if error:
            self.logger.error(f"[KNOWLEDGE] 处理文件 - 文件ID:{file_id}, 状态:{status}, 错误:{error}")
        else:
            self.logger.info(f"[KNOWLEDGE] 处理文件 - 文件ID:{file_id}, 状态:{status}, 分块数:{chunk_count}")

    def log_knowledge_search(self, query: str, results_count: int, file_ids: list = None):
        """记录知识库搜索"""
        file_filter = f"文件ID:{file_ids}" if file_ids else "全部文件"
        self.logger.info(f"[KNOWLEDGE] 搜索知识 - 查询:{query}, 结果数:{results_count}, {file_filter}")


class SearchLogger:
    """搜索操作日志记录器"""

    def __init__(self):
        self.logger = logger

    def log_search_query(self, query: str, intent: str, memories_used: int):
        """记录搜索查询"""
        self.logger.info(f"[SEARCH] 搜索查询 - 查询:{query}, 意图:{intent}, 使用记忆:{memories_used}")

    def log_search_results(self, query: str, results_count: int, intent: str):
        """记录搜索结果"""
        self.logger.info(f"[SEARCH] 搜索结果 - 查询:{query}, 意图:{intent}, 结果数:{results_count}")

    def log_search_answer(self, query: str, answer_length: int, sources_count: int):
        """记录搜索答案生成"""
        self.logger.info(f"[SEARCH] 答案生成 - 查询:{query}, 答案长度:{answer_length}, 来源数:{sources_count}")


# 全局实例
memory_logger = MemoryLogger()
chat_logger = ChatLogger()
knowledge_logger = KnowledgeLogger()
search_logger = SearchLogger()
