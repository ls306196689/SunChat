# SunChat 数据库与数据结构设计

## 数据库选型

### 为什么选择 SQLite + Chroma

| 需求 | SQLite | PostgreSQL | MySQL |
|------|--------|------------|-------|
| 本地运行 | ✅ 内置 | ❌ 需服务 | ❌ 需服务 |
| 零配置 | ✅ | ❌ | ❌ |
| 跨平台 | ✅ | ✅ | ✅ |
| Docker 支持 | ✅ | ✅ | ✅ |
| 性能 (个人规模) | ✅ 足够 | ✅ | ✅ |
| 学习成本 | ⭐ 极低 | ⭐⭐ 低 | ⭐⭐⭐ 中 |

**结论**：个人项目首选 SQLite，未来可迁移到 PostgreSQL

### Chroma 向量数据库

- 内置持久化，无需额外服务
- 支持元数据过滤
- 与 OpenAI 兼容的 API

## SQLite 数据库设计

### 1. 用户表 (users)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    settings TEXT DEFAULT '{}'  -- JSON 格式存储用户设置
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

### 2. 聊天会话表 (chat_sessions)

```sql
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(255),  -- AI 自动生成的会话标题
    summary TEXT,        -- 会话摘要
    is_pinned BOOLEAN DEFAULT 0,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_updated ON chat_sessions(updated_at);
```

### 3. 消息表 (messages)

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role ENUM('user', 'assistant', 'system', 'tool') NOT NULL,
    content TEXT NOT NULL,
    raw_response TEXT,  -- LLM 原始响应 (JSON)
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at);
```

### 4. 记忆表 (memories)

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,  -- 格式: mem_uuid
    user_id INTEGER NOT NULL,
    type ENUM('semantic', 'episodic', 'working') NOT NULL,
    category VARCHAR(50),  -- 如: preference, skill, event
    content TEXT NOT NULL,
    vector_id TEXT,  -- Chroma 中的向量 ID
    confidence REAL DEFAULT 0.5,  -- 0-1
    importance INTEGER DEFAULT 5,  -- 1-10
    is_confirmed BOOLEAN DEFAULT 1,
    metadata TEXT DEFAULT '{}',  -- JSON 扩展字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_memories_user ON memories(user_id);
CREATE INDEX idx_memories_type ON memories(type);
CREATE INDEX idx_memories_category ON memories(category);
CREATE INDEX idx_memories_importance ON memories(importance);
```

**记忆元数据结构：**
```json
// semantic 记忆
{
  "tags": ["编程", "Python"],
  "source": ["chat_123", "doc_456"],
  "entities": [
    {"text": "FastAPI", "type": "technology"},
    {"text": "后端开发", "type": "topic"}
  ]
}

// episodic 记忆
{
  "timestamp": "2026-05-20T14:30:00",
  "event_type": "achievement",
  "duration": "2h",
  "location": "家"
}
```

### 5. 情感记录表 (emotions)

```sql
CREATE TABLE emotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT,
    user_id INTEGER NOT NULL,
    valence REAL,  -- 情绪效价: -1(负面) ~ 1(正面)
    arousal REAL,  -- 激活度: 0(平静) ~ 1(激动)
    dominant_emotion VARCHAR(50),  -- 如: happy, anxious, excited
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_id) REFERENCES memories(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_emotions_memory ON emotions(memory_id);
CREATE INDEX idx_emotions_user ON emotions(user_id);
```

### 6. 知识库文件表 (kb_files)

```sql
CREATE TABLE kb_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,  -- pdf, docx, md, txt, etc.
    file_size INTEGER NOT NULL,  -- 字节数
    status ENUM('uploading', 'processing', 'ready', 'failed') DEFAULT 'uploading',
    error_message TEXT,
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    vector_ids TEXT,  -- JSON 存储所有 chunk 的 vector_id
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_kb_files_user ON kb_files(user_id);
CREATE INDEX idx_kb_files_status ON kb_files(status);
```

### 7. 知识库分块表 (kb_chunks)

```sql
CREATE TABLE kb_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES kb_files(id)
);

CREATE INDEX idx_kb_chunks_file ON kb_chunks(file_id);
CREATE INDEX idx_kb_chunks_vector ON kb_chunks(vector_id);
```

### 8. 搜索历史表 (search_history)

```sql
CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    intent VARCHAR(50),  -- general, academic, news, code
    results_count INTEGER DEFAULT 0,
    used_sources TEXT,  -- JSON 数组
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_search_history_user ON search_history(user_id);
CREATE INDEX idx_search_history_created ON search_history(created_at);
```

### 9. 系统配置表 (system_configs)

```sql
CREATE TABLE system_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    config_type VARCHAR(50),
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO system_configs (config_key, config_value, config_type, description)
VALUES 
    ('llm_api_url', 'http://localhost:11434', 'string', 'LLM API 地址'),
    ('llm_model', 'qwen2.5:7b', 'string', 'LLM 模型名称'),
    ('embedding_model', 'bge-small-zh', 'string', '嵌入模型'),
    ('search_default_source', 'duckduckgo', 'string', '默认搜索源'),
    ('memory_retention_days', '30', 'integer', '记忆保留天数'),
    ('auto_summarize', 'true', 'boolean', '是否自动总结对话');
```

## Chroma 向量集合设计

### Collections

```python
# 1. 用户记忆集合
collection_name: "user_memories"
metadata:
    - user_id (filterable)
    - type (semantic/episodic)
    - category
    - importance
    - created_at

# 2. 知识库分块集合
collection_name: "knowledge_base"
metadata:
    - file_id (filterable)
    - chunk_index
    - source_type

# 3. 搜索索引集合 (缓存搜索结果)
collection_name: "search_cache"
metadata:
    - query_hash
    - intent
    - created_at
```

### 向量元数据示例

```python
# 记忆向量元数据
{
    "user_id": "user_001",
    "type": "semantic",
    "category": "preference",
    "importance": 8,
    "confidence": 0.95,
    "tags": '["咖啡", "手冲"]',
    "created_at": "2026-05-20T10:00:00"
}

# 知识库向量元数据
{
    "file_id": 123,
    "chunk_index": 5,
    "source_type": "pdf",
    "page_number": 15
}
```

## 索引优化建议

### 必需索引
```sql
-- 用户相关查询
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_memories_user ON memories(user_id);

-- 时间范围查询
CREATE INDEX idx_chat_sessions_updated ON chat_sessions(updated_at);
CREATE INDEX idx_search_history_created ON search_history(created_at);

-- 过滤查询
CREATE INDEX idx_kb_files_status ON kb_files(status);
CREATE INDEX idx_memories_type ON memories(type);
```

### 查询性能优化
```sql
-- 覆盖索引示例 (如果 SQLite 版本支持)
CREATE INDEX idx_messages_fast 
ON messages(session_id, created_at) 
INCLUDE (content, role);
```

## 数据迁移策略

### 从 SQLite 迁移到 PostgreSQL (未来)

```sql
-- 导出 SQLite
sqlite3 sunchat.db ".dump" > backup.sql

-- 导入 PostgreSQL
psql -h localhost -U sunchat -d sunchat < backup.sql
```

### 向量数据库迁移

Chroma 支持导出/导入：
```python
import chromadb
from chromadb.config import Settings

# 导出
client = chromadb.Client(Settings(persist_directory="./chroma_db"))
client.persist()

# 迁移时直接复制目录
```

## 备份与恢复

### SQLite 备份
```bash
# 在线备份 (不阻塞)
sqlite3 sunchat.db ".backup 'backup/sunchat_$(date +%Y%m%d).db'"

# 恢复
sqlite3 sunchat.db < backup/sunchat_20260524.db
```

### Chroma 备份
```bash
# 复制持久化目录
cp -r chroma_db backup/chroma_db_$(date +%Y%m%d)
```
