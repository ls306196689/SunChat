"""
Test Fakes - 离线网络层桩
拦截 Ollama HTTP 调用(llm/embedding/model_manager)与 DuckDuckGo 搜索,
保证全量 pytest 在无网络 / 无 Ollama / 慢模型环境下可确定性地快速通过。

设计:
- 不 patch 全局 requests 类(chromadb 遥测等自带 Session 不受影响),
  只替换被测量模块持有的引用: core.llm._http / core.embedding._http /
  core.model_manager.requests / core.search.ddgs 搜索行为。
- 嵌入向量由文本 sha256 确定性生成(同文本同向量),Chroma 可正常做相似度。
"""
import hashlib
import json
import math
import re
from typing import Dict, List

FAKE_CHAT_MODELS = [{"name": "qwen2.5:7b"}, {"name": "nomic-embed-text"}]
# 调用计数与最近 payload 捕获（供测试断言 0 LLM / system 单份 / 多轮历史）
CALLS = {"chat": 0, "embed": 0}
LAST_CHAT_PAYLOADS: List[Dict] = []
# 脚本化 /api/chat 响应队列（Agent tool_calls 场景）：[{"message": {...}}]
SCRIPTED_CHAT: List[Dict] = []


def reset_calls():
    CALLS["chat"] = 0
    CALLS["embed"] = 0
    LAST_CHAT_PAYLOADS.clear()
    SCRIPTED_CHAT.clear()
FAKE_SEARCH_RESULTS = [
    {"title": "Python 语言介绍", "href": "http://example.com/py", "url": "http://example.com/py",
     "body": "Python 是一种解释型编程语言。", "snippet": "Python 是一种解释型编程语言。"},
    {"title": "编程入门", "href": "http://example.com/learn", "url": "http://example.com/learn",
     "body": "编程入门指南。", "snippet": "编程入门指南。"},
]

DEFAULT_REPLY = "好的，这是一条离线模拟回复。"


def fake_embedding(text: str, dim: int = 64) -> List[float]:
    """确定性伪嵌入：sha256(text) 展开为单位向量。"""
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    vec = [(digest[i % len(digest)] + i) / 255.0 for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _extract_prompt_text(payload: Dict) -> str:
    msgs = payload.get("messages", [])
    return " ".join(m.get("content", "") for m in msgs if isinstance(m, dict))


def fake_chat_reply(payload: Dict) -> str:
    """按 prompt 类型返回确定性回复(路由器 JSON / 提取器 JSON / 通用文本)。"""
    text = _extract_prompt_text(payload)

    if "记忆分析器" in text:  # memory_router 分析
        return json.dumps({
            "needs_memory": True,
            "memory_types": ["general"],
            "query_keywords": re.findall(r"[\u4e00-\u9fa5A-Za-z]{2,6}", text)[:3],
            "confidence": 0.9,
            "notes": "offline fake",
        }, ensure_ascii=False)

    if "记忆提取" in text:  # memory_extractor / generate_memory_from_message
        m = re.search(r"用户(?:消息|输入)[:：]\s*(.+)", text)
        user_content = m.group(1).strip().splitlines()[0] if m else ""
        name = re.search(r"我叫([\u4e00-\u9fa5·]{1,8})", user_content)
        if name:
            mem = {"content": f"用户叫{name.group(1)}", "type": "semantic",
                   "category": "name", "importance": 10}
        elif user_content:
            mem = {"content": user_content, "type": "semantic",
                   "category": "general", "importance": 5}
        else:
            return json.dumps({"memories": []}, ensure_ascii=False)
        return json.dumps({"memories": [mem]}, ensure_ascii=False)

    return DEFAULT_REPLY


class FakeResponse:
    def __init__(self, payload, status_code: int = 200, lines: List[bytes] = None):
        self._payload = payload
        self.status_code = status_code
        self._lines = lines

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload

    def iter_lines(self):
        return iter(self._lines or [])


class UnhandledEndpoint(AssertionError):
    """测试触达了未 mock 的端点:说明有新网络调用未被守卫覆盖。"""


class FakeSession:
    headers: Dict = {}

    def post(self, url: str, json=None, timeout=None, stream=False, **kw):
        return dispatch(url, json or {}, stream=stream)

    def get(self, url: str, timeout=None, **kw):
        return dispatch(url, {}, stream=False)


class FakeRequests:
    """core.model_manager 用的 requests 模块替身(仅 .get / .post)。"""

    @staticmethod
    def get(url, timeout=None, **kw):
        return dispatch(url, {}, stream=False)

    @staticmethod
    def post(url, json=None, timeout=None, **kw):
        return dispatch(url, json or {}, stream=False)


def dispatch(url: str, payload: Dict, stream: bool = False) -> FakeResponse:
    if url.endswith("/api/tags"):
        return FakeResponse({"models": FAKE_CHAT_MODELS})
    if url.endswith("/api/chat"):
        CALLS["chat"] += 1
        LAST_CHAT_PAYLOADS.append(payload)
        if SCRIPTED_CHAT and payload.get("tools"):
            # 脚本化 Agent 响应（tool_calls 等）；仅带 tools 的请求从队列消费，
            # 普通对话（无 tools）不受影响
            scripted = SCRIPTED_CHAT.pop(0)
            reply_payload = dict(scripted)
            reply_payload.setdefault("done", False)
            reply_payload.setdefault("eval_count", 8)
            return FakeResponse(reply_payload)
        reply = fake_chat_reply(payload)
        if stream:
            lines = []
            for piece in re.findall(r".{1,8}", reply) or [reply]:
                lines.append(json.dumps(
                    {"message": {"role": "assistant", "content": piece}, "done": False}
                ).encode("utf-8"))
            lines.append(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}).encode("utf-8"))
            return FakeResponse(None, lines=lines)
        return FakeResponse({
            "message": {"role": "assistant", "content": reply},
            "eval_count": 8, "prompt_eval_count": 12,
            "model": payload.get("model", "fake"),
        })
    if url.endswith("/api/embed"):
        inputs = payload.get("input") or []
        if isinstance(inputs, str):
            inputs = [inputs]
        return FakeResponse({"embeddings": [fake_embedding(t) for t in inputs]})
    if url.endswith("/api/embeddings"):
        return FakeResponse({"embedding": fake_embedding(payload.get("prompt", ""))})
    raise UnhandledEndpoint(f"测试中出现未 mock 的 Ollama 端点: {url}")


class FakeDDGS:
    """core.search 用的 DuckDuckGo 替身。"""

    def __init__(self, *a, **kw):
        pass

    def text(self, query, max_results=5, **kw):
        return list(FAKE_SEARCH_RESULTS[:max_results])


def install():
    """把桩装配到各模块引用上(幂等)。返回卸载函数列表的逆操作由 monkeypatch 管理。"""
    import core.llm as llm_mod
    import core.embedding as embed_mod
    import core.model_manager as mm_mod
    import core.search as search_mod
    from unittest import mock

    patchers = []
    fake_session = FakeSession()
    patch_targets = [
        (llm_mod, "_http", fake_session),
        (embed_mod, "_http", fake_session),
        (mm_mod, "requests", FakeRequests),
    ]
    try:
        import core.agent.llm as agent_llm_mod
        patch_targets.append((agent_llm_mod, "_http", fake_session))
    except ImportError:
        pass
    for mod, name, target in patch_targets:
        p = mock.patch.object(mod, name, target)
        p.start()
        patchers.append(p)
    # 搜索服务的 ddgs 实例在 import 时已创建，需替换实例本身
    p = mock.patch.object(search_mod.search_service, "ddgs", FakeDDGS())
    p.start()
    patchers.append(p)
    return patchers


def uninstall(patchers):
    for p in reversed(patchers):
        p.stop()
