"""
SunChat Backend - JSON Parser Utility
统一处理 LLM 输出中的 JSON：剥离 Markdown 代码块围栏 + 截取首个 {...} 块 + 解析。
供 memory_router / memory_extractor / agent / agent_llm / chat_service 复用，
避免 5 处重复的解析逻辑。
"""
import json
import re
from typing import Optional


def strip_code_fences(text: str) -> str:
    """剥离 ```json / ``` 围栏。"""
    t = (text or "").strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def parse_json_response(text: str) -> Optional[dict]:
    """从 LLM 文本输出解析 JSON 对象。

    依次尝试：
    1. 剥离围栏后整体 json.loads
    2. 截取首个 {...} 块再 json.loads（处理 LLM 在 JSON 前后夹带说明文字）

    解析失败返回 None（由调用方决定回退策略）。
    """
    if not text:
        return None
    cleaned = strip_code_fences(text)

    # 1) 整体解析
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        pass

    # 2) 截取首个 {...} 块
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            pass

    return None
