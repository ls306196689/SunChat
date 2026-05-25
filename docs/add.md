  针对你提出的5个问题，我来逐一解决，并推荐**免费的网络搜索工具**替代方案。

---

## 一、免费网络搜索工具推荐

| 工具 | 类型 | 免费额度 | 特点 | 适用场景 |
|-----|------|---------|------|---------|
| **DuckDuckGo API** | 聚合搜索 | 完全免费 | 无需API Key，隐私友好，无速率限制 | 通用搜索首选 |
| **SearXNG** | 自托管元搜索 | 完全免费 | 开源，可自建实例，聚合多个引擎 | 需要可控/私有化部署 |
| **Brave Search API** | 独立搜索 | 2000次/月免费 | 自建索引，结果质量高，无广告 | 对结果质量要求高 |
| **Bing Web Search API** | 商业API | 1000次/月免费 | 结果丰富，文档完善 | 微软生态/小流量 |
| **Google Custom Search** | 商业API | 100次/天免费 | 可定制搜索范围 | 特定站点搜索 |
| **Wikipedia API** | 知识搜索 | 完全免费 | 结构化知识，适合事实查询 | 百科/学术基础查询 |
| **ArXiv API** | 学术论文 | 完全免费 | 论文元数据+PDF链接 | 学术研究 |

### 推荐方案：分层免费搜索架构

```
┌─────────────────────────────────────────┐
│           搜索路由层                     │
│  (根据查询类型选择最优免费源)              │
├─────────────────────────────────────────┤
│  通用查询 ──→ DuckDuckGo (主)            │
│            └──→ SearXNG (备)             │
│  学术查询 ──→ ArXiv + Semantic Scholar   │
│  知识查询 ──→ Wikipedia API              │
│  代码查询 ──→ GitHub API (免费)          │
│  新闻查询 ──→ RSS聚合 + NewsAPI (免费层) │
└─────────────────────────────────────────┘
```

---

## 二、5个关键问题解决方案

### 问题1：项目边界明确化

**明确界定：SunChat = 个人AI助手（非社交应用）**

```
定位声明：
┌─────────────────────────────────────────┐
│  SunChat 是个人智能助手                 │
│  • 1对1 人机对话（无社交功能）          │
│  • 核心：记忆 + 搜索 + 多领域问题解决    │
│  • 用户 = 唯一中心，AI = 专属助手        │
│  • 数据归属：用户完全拥有               │
└─────────────────────────────────────────┘

命名建议（如果担心混淆）：
- 保留 SunChat → 品牌名，通过功能定义消除歧义
- 或改为：SunAssist / SunMemo / 个人AI助手
```

---

### 问题2：关键页面UI原型

#### 页面1：聊天主界面

```
┌─────────────────────────────────────────┐
│  ≡  SunChat                    ⚙️ 👤   │  ← 侧边栏/设置/用户
├─────────────────────────────────────────┤
│                                         │
│  🤖 你好！今天有什么可以帮你的？         │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ 💡 快速入口                      │   │
│  │ [搜索最新新闻] [查看我的记忆]      │   │
│  │ [上传文档] [代码助手]             │   │
│  └─────────────────────────────────┘   │
│                                         │
│  👤 帮我查一下React 19的新特性          │
│                                         │
│  🤖 正在搜索...                        │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ 📰 React 19 主要新特性 (来源)     │   │
│  │ • Actions: 简化表单提交...        │   │
│  │ • useOptimistic: 乐观更新...     │   │
│  │ • 基于你之前的React项目经验...     │   │  ← 记忆关联
│  └─────────────────────────────────┘   │
│                                         │
│  👤 记下来我最近在学这个                 │
│  🤖 ✅ 已记录：你正在学习React 19       │
│                                         │
├─────────────────────────────────────────┤
│  🎤  [输入消息...]              ⬆️ 📎   │
└─────────────────────────────────────────┘
```

#### 页面2：记忆管理中心

```
┌─────────────────────────────────────────┐
│  ← 记忆管理中心              [+ 手动添加] │
├─────────────────────────────────────────┤
│  🔍 搜索记忆...                         │
├─────────────────────────────────────────┤
│  📊 记忆统计                             │
│  总计: 156条 | 本月新增: 23条 | 置信度>90%: 89% │
├─────────────────────────────────────────┤
│  📁 分类浏览                             │
│                                         │
│  🏷️ 个人资料 (12)    🏷️ 工作学习 (45)   │
│  ├─ 职业: 程序员      ├─ 技术栈: React    │
│  ├─ 城市: 北京        ├─ 项目: SunChat   │
│  └─ 生日: 1995...    └─ 目标: 全栈开发   │
│                                         │
│  🏷️ 生活偏好 (34)    🏷️ 重要事件 (28)   │
│  ├─ 饮食: 喜辣        ├─ 2026-05: 辞职   │
│  ├─ 运动: 跑步        ├─ 2026-04: 搬家   │
│  └─ 宠物: 猫(橘子)   └─ 2026-03: 学AI   │
│                                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  选中记忆详情:                           │
│  "用户喜欢手冲咖啡，偏好浅烘焙豆"         │
│  [来源: 2026-05-20对话] [置信度: 95%]   │
│  [编辑] [删除] [标记重要] [查看关联]      │
└─────────────────────────────────────────┘
```

#### 页面3：知识库管理

```
┌─────────────────────────────────────────┐
│  ← 我的知识库              [+ 上传文档]  │
├─────────────────────────────────────────┤
│  📁 文件夹结构                           │
│  ├── 📂 工作文档                        │
│  │   ├── 📄 产品需求文档.pdf (已索引)    │
│  │   └── 📄 技术架构.md (已索引)         │
│  ├── 📂 学习资料                        │
│  │   ├── 📄 React进阶.pdf (索引中...)     │
│  │   └── 🔗 收藏网页: 算法导论 (已抓取)   │
│  └── 📂 个人笔记                        │
│      └── 🎤 语音笔记: 2026-05-24 (已转录)│
├─────────────────────────────────────────┤
│  文档详情: 产品需求文档.pdf               │
│  大小: 2.3MB | 页数: 15 | 状态: ✅ 可搜索 │
│  [预览] [重新索引] [删除] [分享]          │
│                                         │
│  相关问答测试:                           │
│  Q: 这个项目的核心功能是什么？            │
│  A: 根据文档，核心功能包括... [查看来源]   │
└─────────────────────────────────────────┘
```

---

### 问题3：搜索成本评估（免费方案 vs 付费方案）

| 方案 | 月成本 | 适用规模 | 风险 |
|-----|--------|---------|------|
| **纯免费方案** (DuckDuckGo + SearXNG + Wikipedia) | ¥0 | 个人/小团队 | DuckDuckGo可能调整策略 |
| **混合方案** (Brave免费层 + DuckDuckGo) | ¥0 | 中等流量 | 需监控配额 |
| **低成本方案** (Bing 1000次/月 + 免费层) | ¥0-50 | 中小应用 | 微软政策变动 |
| **商业方案** (SerpAPI/Google) | ¥200-2000 | 大规模生产 | 成本高但稳定 |

**推荐：从纯免费方案起步，设置降级策略**

```python
# 搜索降级策略伪代码
async def search(query):
    try:
        return await duckduckgo_search(query)
    except RateLimit:
        try:
            return await searxng_search(query)
        except:
            return await wikipedia_search(query)  # 最终兜底
```

---

### 问题4：向量数据库选型明确化

| 维度 | **Chroma** | **Milvus** | 推荐场景 |
|-----|-----------|-----------|---------|
| **部署复杂度** | 极简单 (`pip install`) | 需Docker/K8s | Chroma: 个人/小项目 |
| **数据规模** | <100万条向量 | 亿级向量 | Milvus: 企业级 |
| **持久化** | 本地文件/SQLite | 专用存储引擎 | Chroma: 单机 |
| **查询性能** | 够用 | 毫秒级大规模 | Milvus: 高并发 |
| **元数据过滤** | 基础支持 | 强大过滤+混合搜索 | Milvus: 复杂查询 |
| **资源占用** | 低（内存<1GB） | 高（需独立服务） | Chroma: 资源受限 |

**SunChat推荐：Chroma（单机版）**

理由：
- 个人助手数据量小（<10万条记忆）
- 部署零门槛，用户可本地运行
- 未来可无缝迁移到Milvus（都支持OpenAI Embedding格式）

```python
# Chroma 快速接入示例
import chromadb
from chromadb.config import Settings

# 本地持久化
client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="./chroma_db"
))

# 创建记忆集合
memory_collection = client.create_collection("user_memories")

# 存储记忆
memory_collection.add(
    documents=["用户喜欢手冲咖啡"],
    metadatas=[{"type": "preference", "confidence": 0.95, "date": "2026-05-20"}],
    ids=["mem_001"]
)

# 语义检索
results = memory_collection.query(
    query_texts=["用户喜欢喝什么"],
    n_results=3
)
```

---

### 问题5：安全设计补充

```
┌─────────────────────────────────────────┐
│           SunChat 安全架构               │
├─────────────────────────────────────────┤
│  1. 身份认证层                           │
│     • 本地模式: 可选密码保护              │
│     • 云端模式: JWT + 双因素认证          │
│     • 生物识别: 指纹/面容（移动端）       │
├─────────────────────────────────────────┤
│  2. 数据加密层                           │
│     • 传输: HTTPS/TLS 1.3                │
│     • 存储: AES-256-GCM                  │
│     • 敏感字段: 额外密钥加密（密码、地址）  │
│     • 密钥管理: 本地Keychain/系统密钥库   │
├─────────────────────────────────────────┤
│  3. 内容安全层                           │
│     • 输入过滤: 防Prompt注入检测          │
│     • 输出过滤: 有害内容识别（本地轻量模型）│
│     • 隐私保护: 自动脱敏（手机号/身份证）   │
│     • 搜索安全: URL黑名单 + 内容分级       │
├─────────────────────────────────────────┤
│  4. 权限控制层                           │
│     • 记忆分级: 公开/普通/敏感/机密       │
│     • 访问日志: 谁看了什么记忆（审计）      │
│     • 数据主权: 用户一键导出/完全删除       │
├─────────────────────────────────────────┤
│  5. 防攻击层                             │
│     • 速率限制: API调用频率控制            │
│     • 搜索隔离: 用户搜索历史不交叉污染      │
│     • 记忆隔离: 多用户严格数据隔离          │
└─────────────────────────────────────────┘
```

**Prompt注入防护示例：**

```python
# 输入预处理
def sanitize_input(user_input):
    # 检测常见注入模式
    injection_patterns = [
        "ignore previous instructions",
        "system prompt",
        "you are now",
        "DAN mode",
        "jailbreak"
    ]
    
    lowered = user_input.lower()
    for pattern in injection_patterns:
        if pattern in lowered:
            return {
                "safe": False,
                "reason": "检测到潜在注入攻击",
                "action": "拒绝处理并记录"
            }
    
    # 长度限制
    if len(user_input) > 10000:
        return {"safe": False, "reason": "输入过长"}
    
    return {"safe": True, "input": user_input}
```

---

## 三、修正后的完整架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    🌅 SunChat 个人AI助手                      │
│              "你的记忆，你的助手，永远免费"                      │
├─────────────────────────────────────────────────────────────┤
│                      用户交互层                              │
│  Web端 / 桌面端(Tauri) / 移动端(Flutter) / 命令行             │
├─────────────────────────────────────────────────────────────┤
│                      安全网关层                                │
│  身份认证 → 输入过滤 → 速率限制 → 审计日志                     │
├─────────────────────────────────────────────────────────────┤
│                      智能核心层                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ 对话引擎 │ │ 记忆系统 │ │ 知识库  │ │ 搜索模块 │           │
│  │ (LLM)   │ │(Chroma) │ │ (RAG)   │ │(免费API)│           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
├─────────────────────────────────────────────────────────────┤
│                      数据存储层                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │聊天记录 │ │ 向量记忆 │ │ 知识文档│ │ 本地配置 │           │
│  │(SQLite) │ │(Chroma) │ │(文件系统)│ │(JSON)  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│  加密: AES-256-GCM | 密钥: 本地Keychain管理                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、免费搜索工具接入代码示例

```python
# 免费搜索聚合器
import asyncio
import aiohttp
from typing import List, Dict

class FreeSearchAggregator:
    def __init__(self):
        self.sources = {
            "duckduckgo": self._search_duckduckgo,
            "wikipedia": self._search_wikipedia,
            "github": self._search_github,
        }
    
    async def search(self, query: str, intent: str = "general") -> List[Dict]:
        """根据意图选择最优免费源"""
        source_map = {
            "general": ["duckduckgo", "wikipedia"],
            "academic": ["arxiv", "semantic_scholar"],
            "code": ["github"],
            "knowledge": ["wikipedia"],
        }
        
        sources = source_map.get(intent, ["duckduckgo"])
        tasks = [self.sources[s](query) for s in sources if s in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并去重排序
        return self._merge_results([r for r in results if not isinstance(r, Exception)])
    
    async def _search_duckduckgo(self, query: str) -> List[Dict]:
        """DuckDuckGo即时答案API（无需Key）"""
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return [{
                    "title": r.get("Text", ""),
                    "url": r.get("FirstURL", ""),
                    "source": "DuckDuckGo",
                    "snippet": r.get("Text", "")
                } for r in data.get("RelatedTopics", [])[:5]]
    
    async def _search_wikipedia(self, query: str) -> List[Dict]:
        """Wikipedia API（完全免费）"""
        url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{query}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [{
                        "title": data.get("title"),
                        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                        "source": "Wikipedia",
                        "snippet": data.get("extract", "")[:200]
                    }]
                return []
```

---

需要我把某个模块展开成完整可运行的代码（比如记忆系统的CRUD + 向量检索），或者设计具体的数据库Schema吗？