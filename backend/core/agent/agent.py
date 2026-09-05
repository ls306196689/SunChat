"""
SunChat Backend - Agent Core
Ollama 原生 tool_calls 循环（替代伪 ReAct JSON 文本，修 A1/A3/A4/A7）。

- 无状态：历史/消息由调用方传入，循环内 messages 为局部变量
- role:"tool" 消息紧跟带 tool_calls 的 assistant 消息、带 name（Ollama 合法序）
- 工具结果 content 一律 json.dumps(ensure_ascii=False)
- 纯文本回退：模型不支持 tools / 不产 tool_calls / 解析失败 → 直接返回文本答案
- max_iterations 兜底
"""
import json
from typing import List, Dict, Optional, Tuple

from core.agent.schema import ToolResult
from core.agent.tools import get_openai_tool_schemas, execute_tool
from core.agent.llm import agent_llm
from utils.logger import logger


DEFAULT_SYSTEM_PROMPT = """你是 SunChat 个人助理 Agent，可以调用工具来完成任务。

可用能力：查询/保存用户记忆、联网搜索、检索知识库文档。
规则：
1. 需要用户个人信息时先查记忆，再回答；用户主动告知的重要信息要调用 memory_create 保存。
2. 时效性问题（新闻/最新）用 web_search；上传文档内容用 knowledge_search。
3. 能直接回答的问题不要调用工具。
4. 中文回答，简洁准确；引用工具结果时说明依据。"""


def _normalize_arguments(raw) -> Dict:
    """tool_calls.function.arguments 可能是 dict 或 JSON 字符串。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


class Agent:
    """Agent：原生 tool_calls 多轮循环（无状态，可并发安全使用）。"""

    def __init__(self, max_iterations: int = 5, system_prompt: str = None):
        self.default_max_iterations = max_iterations
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def run(self, user_input: str, user_id: int = 1,
            history: List[Dict] = None, model: str = None,
            max_iterations: int = None) -> Dict:
        """执行 Agent 循环。

        Args:
            user_input: 用户输入
            user_id: 注入工具的用户身份（LLM 不可见不可改）
            history: 可选多轮历史 [{"role","content"}]
        Returns:
            {"content": 最终答案, "tool_trace": [...], "iterations": n, "mode": "tools"|"text"}
        """
        max_iter = max_iterations or self.default_max_iterations
        messages: List[Dict] = [{"role": "system", "content": self.system_prompt}]
        for h in (history or []):
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_input})

        tool_trace: List[Dict] = []
        schemas = get_openai_tool_schemas()

        for i in range(max_iter):
            try:
                resp = agent_llm.generate(messages, tools=schemas, model=model)
            except Exception as e:
                logger.error(f"[AGENT] LLM 调用失败(轮{i + 1}): {e}")
                # 纯文本回退：不带 tools 再试一轮
                try:
                    resp = agent_llm.generate(messages, tools=None, model=model)
                except Exception as e2:
                    return {"content": "", "tool_trace": tool_trace,
                            "iterations": i, "mode": "tools", "error": str(e2)}
                return {"content": resp["message"].get("content", ""),
                        "tool_trace": tool_trace, "iterations": i + 1,
                        "mode": "text"}

            msg = resp.get("message", {}) or {}
            calls = msg.get("tool_calls") or []

            if not calls:
                # 无工具调用 → 最终答案（含"模型不支持 tools 直接给文本"的回退）
                return {"content": msg.get("content", ""),
                        "tool_trace": tool_trace, "iterations": i + 1,
                        "mode": "tools" if tool_trace else "text"}

            # 追加 assistant（带 tool_calls）+ 每个 tool 结果（合法相邻顺序）
            messages.append({"role": "assistant",
                             "content": msg.get("content", ""),
                             "tool_calls": calls})
            for tc in calls:
                fn = (tc.get("function") or {})
                name = fn.get("name", "")
                args = _normalize_arguments(fn.get("arguments"))
                result: ToolResult = execute_tool(name, args, user_id=user_id)
                payload = result.to_dict()
                tool_trace.append({"tool": name, "arguments": args,
                                   "success": result.success,
                                   "summary": _summarize(payload)})
                messages.append({
                    "role": "tool",
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                    "name": name,
                })

        logger.warning(f"[AGENT] 达到最大迭代 {max_iter}，强制终止")
        return {"content": "（已达到最大工具调用轮次，以下是目前的结果）" +
                "\n".join(t["summary"] for t in tool_trace if t["summary"]),
                "tool_trace": tool_trace, "iterations": max_iter,
                "mode": "tools"}

    def run_simple(self, user_input: str, user_id: int = 1,
                   model: str = None) -> Dict:
        """纯文本单轮（无工具）：用于能力探测失败时的降级路径。"""
        return self.run(user_input, user_id=user_id, model=model,
                        max_iterations=1)


def _summarize(payload: Dict, limit: int = 120) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        text = str(payload)
    return text[:limit] + ("…" if len(text) > limit else "")


# 全局无状态实例
agent = Agent()
