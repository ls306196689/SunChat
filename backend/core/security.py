"""
SunChat Backend - Security Utilities
"""
import re
from typing import Dict, Tuple


# 常见注入攻击模式
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|prior)\s+(instructions?|prompts?|commands?)",
    r"you\s+(are|have)\s+been\s+(disabled|programmed|coded)",
    r"system\s+(prompt|message|role)",
    r"DAN\s+mode|jailbreak",
    r"ignore\s+(my|your)\s+(previous|earlier)",
    r"you\s+are\s+(now|a|an)",
]

# 敏感词列表（可扩展）
# 注意：仅保留"词本身即高危"的词。裸 "key"/"token"/"secret" 会误杀正常技术提问
# （如"如何轮换 API token"），且对话文本不含真实凭据，拦截无收益。
# 日志落盘前的脱敏统一走 mask_sensitive_data（email/手机号/身份证号）。
SENSITIVE_WORDS = [
    "password",
]


def sanitize_input(user_input: str) -> Tuple[bool, str]:
    """
    清理和验证用户输入

    Args:
        user_input: 用户输入

    Returns:
        (是否安全, 错误消息)
    """
    # 长度限制
    if len(user_input) > 10000:
        return False, "输入过长"

    # 检测注入攻击
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, user_input, re.IGNORECASE):
            return False, "检测到潜在注入攻击"

    # 检测敏感词
    for word in SENSITIVE_WORDS:
        if word in user_input.lower():
            return False, f"输入包含敏感词: {word}"

    return True, ""


def mask_sensitive_data(text: str) -> str:
    """
    自动脱敏敏感信息

    Args:
        text: 原始文本

    Returns:
        脱敏后的文本
    """
    # 邮箱
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', text)
    # 手机号
    text = re.sub(r'1[3-9]\d{9}', '[PHONE]', text)
    # 身份证号
    text = re.sub(r'\d{17}[\dX]', '[ID]', text)

    return text
