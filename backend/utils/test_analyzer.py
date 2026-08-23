"""
SunChat Backend - Automated Test Analysis
测试完成后自动读取日志并分析功能正确性
"""
import os
import re
import json
import glob
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 日志文件路径
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)


def get_latest_log_file():
    """获取最新的日志文件"""
    log_files = glob.glob(os.path.join(LOG_DIR, "sunchat_*.log"))
    if log_files:
        non_empty = [f for f in log_files if os.path.getsize(f) > 0]
        if non_empty:
            return max(non_empty, key=os.path.getctime)
        return max(log_files, key=os.path.getctime)
    return os.path.join(LOG_DIR, f"sunchat_{datetime.now().strftime('%Y%m%d')}.log")


LOG_FILE = get_latest_log_file()


class TestAnalyzer:
    """测试分析器"""

    def __init__(self, log_file: str = None):
        self.log_file = log_file or LOG_FILE
        self.results = {
            'test_passes': [],
            'test_fails': [],
            'memory_operations': [],
            'chat_operations': [],
            'knowledge_operations': [],
            'search_operations': [],
            'analysis_timestamp': datetime.now().isoformat()
        }

    def read_logs(self) -> List[str]:
        """读取日志文件"""
        if not os.path.exists(self.log_file):
            return []

        with open(self.log_file, 'r', encoding='utf-8') as f:
            return f.readlines()

    def parse_log_line(self, line: str) -> Optional[Dict]:
        """解析单行日志"""
        # 格式: 2026-06-06 21:07:56 | INFO     | sunchat | [MEMORY] 创建记忆
        # 注意: 级别名称后可能有额外空格
        pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s+\| (\w+) \| (.+)$'
        match = re.match(pattern, line.strip())

        if match:
            timestamp, level, name, message = match.groups()
            return {
                'timestamp': timestamp,
                'level': level,
                'message': message
            }
        return None

    def analyze_memory_operations(self, logs: List[str]) -> List[Dict]:
        """分析记忆操作"""
        operations = []
        for line in logs:
            parsed = self.parse_log_line(line)
            if not parsed:
                continue

            msg = parsed['message']

            # 记忆创建
            if '[MEMORY] 创建记忆' in msg or '[MEMORY] 创建记忆成功' in msg:
                # 提取信息
                match = re.search(r'用户:(\d+), 类型:(\w+), 分类:(\w+), 内容:([^,]+)', msg)
                if match:
                    user_id, mtype, category, content = match.groups()
                    operations.append({
                        'type': 'create',
                        'user_id': int(user_id),
                        'type': mtype,
                        'category': category,
                        'content': content[:50],
                        'timestamp': parsed['timestamp']
                    })

            # 记忆搜索
            elif '[MEMORY] 搜索记忆' in msg or '[MEMORY] 搜索记忆完成' in msg:
                match = re.search(r'用户:(\d+), 查询:([^,]+), 结果数:(\d+), 状态:(\w+)', msg)
                if match:
                    user_id, query, results_count, status = match.groups()
                    operations.append({
                        'type': 'search',
                        'user_id': int(user_id),
                        'query': query[:30],
                        'results_count': int(results_count),
                        'status': status,
                        'timestamp': parsed['timestamp']
                    })

            # 记忆提取
            elif '[CHAT] 记忆提取' in msg:
                match = re.search(r'提取到 (\d+) 条记忆', msg)
                if match:
                    operations.append({
                        'type': 'extract',
                        'memories_count': int(match.group(1)),
                        'timestamp': parsed['timestamp']
                    })

        return operations

    def analyze_chat_operations(self, logs: List[str]) -> List[Dict]:
        """分析聊天操作"""
        operations = []
        for line in logs:
            parsed = self.parse_log_line(line)
            if not parsed:
                continue

            msg = parsed['message']

            # 消息发送
            if '[CHAT] 用户消息' in msg:
                match = re.search(r'用户:(\d+), 会话:(\d+), 内容:([^,]+)', msg)
                if match:
                    user_id, session_id, content = match.groups()
                    operations.append({
                        'type': 'message_send',
                        'user_id': int(user_id),
                        'session_id': int(session_id),
                        'content': content[:50],
                        'timestamp': parsed['timestamp']
                    })

            # 记忆上下文
            elif '[CHAT] 构建记忆上下文' in msg:
                match = re.search(r'上下文数:(\d+)', msg)
                if match:
                    operations.append({
                        'type': 'memory_context',
                        'context_count': int(match.group(1)),
                        'timestamp': parsed['timestamp']
                    })

            # AI 响应
            elif '[CHAT] 处理完成' in msg:
                match = re.search(r'响应长度:(\d+), 新记忆:(\d+)', msg)
                if match:
                    operations.append({
                        'type': 'ai_response',
                        'response_length': int(match.group(1)),
                        'new_memories': int(match.group(2)),
                        'timestamp': parsed['timestamp']
                    })

        return operations

    def analyze_knowledge_operations(self, logs: List[str]) -> List[Dict]:
        """分析知识库操作"""
        operations = []
        for line in logs:
            parsed = self.parse_log_line(line)
            if not parsed:
                continue

            msg = parsed['message']

            if '[KNOWLEDGE]' in msg:
                # 文件上传
                if '上传文件' in msg:
                    match = re.search(r'文件ID:(\d+), 文件名:(\w+\.\w+), 类型:(\w+), 大小:(\d+)', msg)
                    if match:
                        operations.append({
                            'type': 'file_upload',
                            'file_id': int(match.group(1)),
                            'filename': match.group(2),
                            'file_type': match.group(3),
                            'size': int(match.group(4)),
                            'timestamp': parsed['timestamp']
                        })

                # 文件处理
                elif '处理文件' in msg:
                    match = re.search(r'文件ID:(\d+), 状态:(\w+), 分块数:(\d+)', msg)
                    if match:
                        operations.append({
                            'type': 'file_process',
                            'file_id': int(match.group(1)),
                            'status': match.group(2),
                            'chunk_count': int(match.group(3)),
                            'timestamp': parsed['timestamp']
                        })

                # 知识搜索
                elif '搜索知识' in msg:
                    match = re.search(r'查询:([^,]+), 结果数:(\d+)', msg)
                    if match:
                        operations.append({
                            'type': 'knowledge_search',
                            'query': match.group(1)[:30],
                            'results_count': int(match.group(2)),
                            'timestamp': parsed['timestamp']
                        })

        return operations

    def analyze_search_operations(self, logs: List[str]) -> List[Dict]:
        """分析搜索操作"""
        operations = []
        for line in logs:
            parsed = self.parse_log_line(line)
            if not parsed:
                continue

            msg = parsed['message']

            if '[SEARCH]' in msg:
                # 搜索查询
                if '搜索查询' in msg:
                    match = re.search(r'查询:([^,]+), 意图:(\w+), 使用记忆:(\d+)', msg)
                    if match:
                        operations.append({
                            'type': 'search_query',
                            'query': match.group(1)[:30],
                            'intent': match.group(2),
                            'memories_used': int(match.group(3)),
                            'timestamp': parsed['timestamp']
                        })

                # 搜索结果
                elif '搜索结果' in msg:
                    match = re.search(r'查询:([^,]+), 意图:(\w+), 结果数:(\d+)', msg)
                    if match:
                        operations.append({
                            'type': 'search_results',
                            'query': match.group(1)[:30],
                            'intent': match.group(2),
                            'results_count': int(match.group(3)),
                            'timestamp': parsed['timestamp']
                        })

        return operations

    def analyze(self) -> Dict:
        """分析日志文件"""
        logs = self.read_logs()

        self.results['memory_operations'] = self.analyze_memory_operations(logs)
        self.results['chat_operations'] = self.analyze_chat_operations(logs)
        self.results['knowledge_operations'] = self.analyze_knowledge_operations(logs)
        self.results['search_operations'] = self.analyze_search_operations(logs)

        # 统计
        self.results['statistics'] = {
            'total_memory_operations': len(self.results['memory_operations']),
            'total_chat_operations': len(self.results['chat_operations']),
            'total_knowledge_operations': len(self.results['knowledge_operations']),
            'total_search_operations': len(self.results['search_operations']),
            'total_logs': len(logs)
        }

        return self.results

    def generate_report(self, output_file: str = None) -> str:
        """生成分析报告"""
        self.analyze()

        report = []
        report.append("=" * 60)
        report.append("SunChat 自动化测试分析报告")
        report.append("=" * 60)
        report.append(f"分析时间: {self.results['analysis_timestamp']}")
        report.append(f"日志文件: {self.log_file}")
        report.append("")

        report.append("【统计概览】")
        stats = self.results['statistics']
        report.append(f"  总日志条数: {stats['total_logs']}")
        report.append(f"  记忆操作数: {stats['total_memory_operations']}")
        report.append(f"  聊天操作数: {stats['total_chat_operations']}")
        report.append(f"  知识库操作数: {stats['total_knowledge_operations']}")
        report.append(f"  搜索操作数: {stats['total_search_operations']}")
        report.append("")

        # 记忆操作分析
        report.append("【记忆操作分析】")
        for op in self.results['memory_operations']:
            report.append(f"  [{op['type'].upper()}] {op.get('timestamp', '')}")
            report.append(f"    {op}")
        report.append("")

        # 聊天操作分析
        report.append("【聊天操作分析】")
        for op in self.results['chat_operations']:
            report.append(f"  [{op['type'].upper()}] {op.get('timestamp', '')}")
            report.append(f"    {op}")
        report.append("")

        # 知识库操作分析
        report.append("【知识库操作分析】")
        for op in self.results['knowledge_operations']:
            report.append(f"  [{op['type'].upper()}] {op.get('timestamp', '')}")
            report.append(f"    {op}")
        report.append("")

        # 搜索操作分析
        report.append("【搜索操作分析】")
        for op in self.results['search_operations']:
            report.append(f"  [{op['type'].upper()}] {op.get('timestamp', '')}")
            report.append(f"    {op}")
        report.append("")

        report.append("=" * 60)
        report.append("分析完成")
        report.append("=" * 60)

        report_text = "\n".join(report)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)

        return report_text


def run_test_with_analysis(test_func, *args, **kwargs):
    """运行测试并自动分析"""
    from utils.logger import logger, LOG_DIR

    # 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)

    # 记录测试开始
    logger.info(f"=" * 60)
    logger.info("开始执行测试")
    logger.info(f"=" * 60)

    # 运行测试
    result = test_func(*args, **kwargs)

    # 记录测试结束
    logger.info(f"=" * 60)
    logger.info("测试执行完成")
    logger.info(f"=" * 60)

    # 分析日志
    analyzer = TestAnalyzer()
    analysis_results = analyzer.analyze()
    report = analyzer.generate_report()

    # 打印分析报告
    print("\n" + report)

    # 返回测试结果
    return result, analysis_results


# 全局实例
test_analyzer = TestAnalyzer()
