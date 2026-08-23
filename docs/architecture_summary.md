# SunChat 聊天系统架构概览

> 该文档对当前代码库实现的整体结构、关键模块以及数据流进行归纳，便于后续维护与扩展。所有路径均为项目根目录的相对路径。

---

## 1. 总体结构图
```
+-------------------+        +-----------------+        +-----------------+
|   前端 (Vue 3)   |  <--- |   后端 (FastAPI) |  <--- |   本地模型服务    |
|  - Vite dev (5173) |      |  - /api/v1/*      |      |  - Ollama LLM      |
|  - Naive UI       |      |  - /chat, /memories, /search, /knowledge |
|  - Pinia 状态管理 |      |  - services: chat, memory, search, knowledge |
+-------------------+        +-----------------+        +-----------------+
        |                     |                     |
        |                     |                     |
        v                     v                     v
+-------------------+  +-----------------+  +-----------------+
|   向量库 (Chroma) |  |   SQLite DB       |  |   DuckDuckGo API  |
|   (占位, 未完全集成) |  |   - ChatSession   |  |   - 免费文本搜索 |
+-------------------+  |   - Message       |  +-----------------+
                       |   - Memory        |
                       |   - Emotion       |
                       |   - KBFile / KBChunk |
                       +-----------------+
```

---

## 2. 前端（`frontend/`）
| 位置 | 说明 |
|------|------|
| `src/` | Vue 3 单文件组件，使用 **Naive UI** 进行 UI 渲染。主要页面：`ChatView.vue`、`MemoriesView.vue`、`SettingsView.vue` 等。 |
| `src/stores/` | 使用 **Pinia** 管理全局状态：`chat.js`（会话、消息、发送），`memory.js`（记忆 CRUD），`theme.js`（暗/亮主题） |
| `src/components/ui/MessageItem.vue` | 渲染单条聊天记录，支持 loading 动画（占位的 assistant 消息） |
| `vite.config.js` | 开发服务器端口 `5173`，`/api` 代理到后端 `http://localhost:8000` |
| `package.json` | 依赖：`vue@3`、`naive-ui`、`pinia`、`axios` 等 |

**启动方式**：`npm run dev`（或通过根目录的 `start.sh` 脚本）

---

## 3. 后端（`backend/`）
### 3.1 主入口
- **`app/main.py`**：创建 `FastAPI` 实例，挂载路由、CORS 中间件。
- **`app/config.py`**：`pydantic-settings` 配置，包含 LLM、Embedding、数据库等地址。

### 3.2 API 路由（`app/api/v1/routes/`）
| 路由文件 | 主要功能 |
|-----------|----------|
| `auth.py` | mock 注册/登录，返回固定 `user_local` 与 `mock_token` |
| `chat.py` | `/chat/messages`（发送消息）<br>`/chat/sessions`（创建/列出/切换会话） |
| `memories.py` | 记忆的增删改查、搜索、统计 |
| `search.py` | 通过 `search_service` 进行意图路由 + DuckDuckGo 搜索 |
| `knowledge.py` | 文件上传、列表、删除、简单 QA（占位实现） |
| `health.py` | 健康检查，返回 LLM、搜索服务可用性 |

### 3.3 服务层（`services/`）
- **`chat_service.py`**：会话创建、消息分页、记忆构建、LLM 调用包装。
- **`memory_service.py`**：记忆的创建、关键词搜索（简化实现）、更新、删除、统计、情感记录。
- **`knowledge_service.py`**：文件元信息记录、分块存储、模拟 QA。
- **`search_service.py`**：包装 `core.search.SearchService`，提供 `search` 与 `route_query`。

### 3.4 核心工具（`core/`）
| 文件 | 功能 |
|------|------|
| `llm.py` | Ollama 客户端封装，提供 `chat`、`generate`、`list_models`、`check_availability` |
| `embedding.py` | Ollama 嵌入模型封装，返回向量并可列出模型 |
| `search.py` | 基于 **DuckDuckGo** 的文本搜索 + 简单意图分类（新闻、学术、商务、代码、通用） |
| `security.py` | 输入注入检测、敏感词过滤（目前未在路由中调用） |

### 3.5 数据层（`models/`）
- **SQLAlchemy + SQLite**（`settings.DATABASE_URL = "sqlite:///./data/sunchat.db"`）
- 关键模型：
  - `User`、`ChatSession`、`Message`
  - `Memory`（语义/情景记忆），`Emotion`
  - `KBFile`、`KBChunk`
  - `SearchHistory`
- **向量库**：`core/search.py` 已实例化 `SearchService`，`core/embedding.py` 实例化 `EmbeddingService`，但实际向量存储仍使用 **Chroma**（占位，仅在 `knowledge_service` 中记录 `vector_id`）

---

## 4. 大模型与向量服务
| 项目 | 说明 |
|------|------|
| **Ollama** | 本地部署的 LLM（默认 `qwen2.5:7b`）和嵌入模型（默认 `nomic-embed-text`）。通过 `http://localhost:11434/api/*` 交互。 |
| **LLM 调用** | `core/llm.py` 中的 `chat` 与 `generate` 方法封装了非流式请求，后端 `chat.py` 使用 `generate_response`（同步 `requests.post`）。 |
| **Embedding** | `EmbeddingService.embed(text)` 返回向量数组，可用于后续向量检索（目前仅在记忆创建时调用，未写入 Chroma）。 |

---

## 5. 搜索模块
- **DuckDuckGo**（`duckduckgo_search.DDGS`）负责实际网页抓取。
- **意图路由**（`core/search.SearchService._route_query`）使用正则匹配关键词，将查询分为 `news`、`academic`、`commerce`、`code`、`general`。
- **查询增强**：若提供记忆上下文，会把前几条记忆拼接到搜索词后。
- **结果**：返回原始 DuckDuckGo 条目列表（标题、URL、摘要），前端直接渲染。

---

## 6. 记忆系统（Memory）
- **三层模型（概念层）**：
  1. **工作记忆** – 最近 5‑10 轮对话（在前端 `MessageItem` 中即时展示）。
  2. **情景记忆** – 事件型记忆（`type='episodic'`），带时间戳、参与者、情感等。
  3. **语义记忆** – 长期偏好/知识（`type='semantic'`），存储向量 ID、重要性评分。
- **提取**：`ChatService.generate_memory_from_message` 使用 LLM 生成 JSON 格式记忆，随后 `MemoryService.create_memory` 将文本写入 SQLite 并调用 `embedding_service.embed` 生成向量。
- **检索**：目前为 **关键字匹配 + importance 排序**（`MemoryService.search_memories`），未来可替换为 Chroma 向量相似度搜索。
- **统计**：`MemoryService.get_stats` 提供总数、按类型分布、平均置信度。

---

## 7. 知识库（Knowledge Base）
- **文件上传**：`knowledge_service.upload_file` 仅记录元信息（文件名、类型、大小），状态 `uploading` → `ready`（在 `process_file` 中完成分块与向量化，占位实现）。
- **问答**：`knowledge_service.qa` 目前返回模拟答案，真实实现应当使用向量检索后交给 LLM 生成。
- **后续**：实现文档分块、向量化、元数据索引、跨文件检索等。

---

## 8. 安全与认证
- **输入过滤**：`core/security.sanitize_input` 与 `mask_sensitive_data` 已实现，但在路由层尚未调用（可在 `app/dependencies.py` 中统一挂载）。
- **认证**：`auth.py` 仅返回固定用户 `user_local` 与 `mock_token`，适用于本地演示。正式环境应接入 JWT 或 OAuth。
- **日志**：`request.js` 对 HTTP 错误统一打印，后端使用 `print`（可替换为 `loguru`/`structlog`）记录异常。

---

## 9. 部署与启动
- **本地启动**：根目录提供 `start.sh` 脚本，一键启动后端 (`uvicorn`) + 前端 (`npm run dev`) 并在 Ctrl+C 时统一退出。
- **Docker**（未在仓库中实现）可使用 `docker-compose.yml`（位于 `deployment/`）将后端、前端、Ollama、Chroma 统一容器化。
- **环境变量**：`.env`（由 `pydantic-settings` 自动读取）可覆盖 `LLM_API_URL`、`EMBEDDING_API_URL`、`DATABASE_URL` 等。

---

## 10. 未来改进路线（Roadmap）
1. **流式对话**：使用 `uvicorn` 的 SSE 或 WebSocket，将 Ollama `stream=True` 的结果实时推送给前端。
2. **向量检索完整集成**：在 `MemoryService.search_memories` 中调用 Chroma，实现语义相似度搜索。
3. **完整 RAG**：实现 `knowledge_service.process_file` 的分块、向量化、检索 + LLM 生成答案。
4. **安全增强**：在 FastAPI 中全局使用 `Depends(sanitize_input)`，对所有用户输入进行注入检测。
5. **真实认证**：接入 JWT、密码哈希、刷新 token 等机制。
6. **Docker 化**：提供 `Dockerfile` 与 `docker-compose.yml`，一键部署整个系统（包括 Ollama、Chroma、PostgreSQL）。
7. **多端同步**：使用端到端加密的云同步（例如通过 WebDAV 或自建同步服务）实现跨设备记忆共享。
8. **插件体系**：基于 FastAPI 的插件机制，允许外部 Agent（如工具调用、工具插件）接入系统。

---

*本文档由 `start.sh` 脚本自动生成的系统结构信息以及代码审阅手动整理而成，旨在帮助开发者快速了解 SunChat 项目当前实现情况。*