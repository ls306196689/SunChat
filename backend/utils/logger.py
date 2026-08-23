"""
SunChat Backend - Logger Utility
提供统一的日志记录功能
"""
import logging
import os
from datetime import datetime
from typing import Optional

# 创建日志目录
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
LOG_FILE = os.path.join(LOG_DIR, f"sunchat_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_logger(name: str = 'sunchat') -> logging.Logger:
    """获取配置好的日志器"""
    logger = logging.getLogger(name)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 文件处理器
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)

    return logger


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
