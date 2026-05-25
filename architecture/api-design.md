# SunChat API 接口设计

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **Authentication**: 
  - 本地模式: 无认证 (默认)
  - 云端模式: Bearer Token (JWT)
- **Content-Type**: `application/json`
- **Response Format**: Standardized

## 通用响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "timestamp": "2026-05-24T10:00:00Z"
}
```

## 认证相关 API

### 1. 用户注册

```
POST /auth/register
```

**Request**
```json
{
  "username": "string (3-20 chars)",
  "email": "string",
  "password": "string (8+ chars)"
}
```

**Response**
```json
{
  "code": 201,
  "message": "注册成功",
  "data": {
    "user_id": "user_xxx",
    "username": "xxx",
    "token": "jwt_token"
  }
}
```

### 2. 用户登录

```
POST /auth/login
```

**Request**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response**
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "user_id": "user_xxx",
    "username": "xxx",
    "token": "jwt_token",
    "expires_in": 86400
  }
}
```

### 3. 刷新 Token

```
POST /auth/refresh
Headers: Authorization: Bearer <refresh_token>
```

### 4. 获取当前用户

```
GET /auth/me
Headers: Authorization: Bearer <access_token>
```

## 聊天相关 API

### 5. 创建会话

```
POST /chat/sessions
```

**Request**
```json
{
  "title": "string (可选)",
  "initial_message": "string (可选)"
}
```

**Response**
```json
{
  "code": 201,
  "message": "会话创建成功",
  "data": {
    "session_id": "session_xxx",
    "title": "默认标题",
    "created_at": "2026-05-24T10:00:00Z"
  }
}
```

### 6. 发送消息

```
POST /chat/messages
```

**Request**
```json
{
  "session_id": "session_xxx",
  "content": "用户问题",
  "memory_context": true,  // 是否使用记忆
  "search_enabled": true,  // 是否启用搜索
  "model": "qwen2.5:7b"    // 可选，指定模型
}
```

**Response (Stream)**
```
data: {"type": "thinking", "content": "正在思考..."}
data: {"type": "search", "query": "搜索词", "status": "start"}
data: {"type": "search_result", "results": [...]}
data: {"type": "memory", "memories": [...]}
data: {"type": "answer", "content": "回答内容", "is_complete": false}
data: {"type": "answer", "content": "继续回答", "is_complete": true}
data: {"type": "memory_update", "memories_created": 2}
data: {"type": "usage", "tokens": 150, "time": "1.2s"}
```

**Response (非流式)**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "response": "回答内容",
    "memory_updates": [...],
    "search_results": [...],
    "tokens_used": 150
  }
}
```

### 7. 获取会话消息历史

```
GET /chat/sessions/{session_id}/messages
Query: page=1&limit=20
```

**Response**
```json
{
  "code": 200,
  "data": {
    "session_id": "session_xxx",
    "title": "会话标题",
    "messages": [
      {
        "id": "msg_xxx",
        "role": "user",
        "content": "用户问题",
        "created_at": "2026-05-24T10:00:00Z"
      },
      {
        "id": "msg_xxx",
        "role": "assistant",
        "content": "AI 回答",
        "created_at": "2026-05-24T10:00:05Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

### 8. 更新会话标题

```
PATCH /chat/sessions/{session_id}
```

**Request**
```json
{
  "title": "新标题"
}
```

### 9. 删除会话

```
DELETE /chat/sessions/{session_id}
```

## 记忆相关 API

### 10. 查询记忆

```
GET /memories
Query: 
  - type: semantic/episodic/working
  - category: 预约
  - page=1&limit=20
```

**Response**
```json
{
  "code": 200,
  "data": {
    "total": 100,
    "memories": [
      {
        "id": "mem_xxx",
        "type": "semantic",
        "category": "preference",
        "content": "用户喜欢手冲咖啡",
        "confidence": 0.95,
        "importance": 8,
        "tags": ["咖啡", "手冲"],
        "created_at": "2026-05-20T10:00:00Z"
      }
    ]
  }
}
```

### 11. 搜索记忆 (语义检索)

```
POST /memories/search
```

**Request**
```json
{
  "query": "用户喜欢什么饮料",
  "top_k": 5,
  "filters": {
    "type": "semantic",
    "category": "preference"
  }
}
```

**Response**
```json
{
  "code": 200,
  "data": {
    "query": "用户喜欢什么饮料",
    "results": [
      {
        "memory_id": "mem_xxx",
        "content": "用户喜欢手冲咖啡，偏好浅烘焙豆",
        "score": 0.92,
        "metadata": {"tags": ["咖啡", "手冲"]}
      }
    ]
  }
}
```

### 12. 创建记忆

```
POST /memories
```

**Request**
```json
{
  "content": "用户养了一只叫橘子的猫",
  "type": "semantic",
  "category": "pet",
  "tags": ["宠物", "猫"],
  "importance": 7
}
```

### 13. 更新记忆

```
PUT /memories/{memory_id}
```

**Request**
```json
{
  "content": "用户养了两只猫，橘子和奶茶",
  "confidence": 0.98,
  "importance": 9
}
```

### 14. 删除记忆

```
DELETE /memories/{memory_id}
```

### 15. 获取记忆统计

```
GET /memories/stats
```

**Response**
```json
{
  "code": 200,
  "data": {
    "total_count": 156,
    "by_type": {
      "semantic": 120,
      "episodic": 30,
      "working": 6
    },
    "by_category": {
      "preference": 50,
      "skill": 30,
      "event": 40
    },
    "avg_confidence": 0.92
  }
}
```

## 搜索相关 API

### 16. 执行搜索

```
POST /search
```

**Request**
```json
{
  "query": "React 19 新特性",
  "intent": "general",
  "sources": ["duckduckgo", "wikipedia"],
  "use_memory_context": true
}
```

**Response**
```json
{
  "code": 200,
  "data": {
    "query": "React 19 新特性",
    "intent": "general",
    "results": [
      {
        "title": "React 19 新特性介绍",
        "url": "https://example.com/react-19",
        "source": "DuckDuckGo",
        "snippet": "React 19 引入了 Actions、useOptimistic 等新特性...",
        "score": 0.95,
        "metadata": {
          "publish_date": "2026-05-20",
          "author": "React Team"
        }
      }
    ],
    "used_memory": [
      {"id": "mem_xxx", "content": "用户在学习 React"}
    ]
  }
}
```

### 17. 搜索建议

```
GET /search/suggest
Query: q=react
```

**Response**
```json
{
  "code": 200,
  "data": {
    "query": "react",
    "suggestions": [
      "react 19",
      "react hooks",
      "react native",
      "react vs vue"
    ]
  }
}
```

## 知识库相关 API

### 18. 上传文件

```
POST /kb/upload
Content-Type: multipart/form-data
```

**Form Data**
```
file: <file>
metadata: {"category": "学习资料"}
```

**Response**
```json
{
  "code": 201,
  "message": "文件上传成功，正在处理",
  "data": {
    "file_id": 123,
    "filename": "React进阶.pdf",
    "status": "processing"
  }
}
```

### 19. 查询知识库文件

```
GET /kb/files
Query: page=1&limit=10&status=ready
```

**Response**
```json
{
  "code": 200,
  "data": {
    "files": [
      {
        "id": 123,
        "filename": "React进阶.pdf",
        "original_name": "React Advanced.pdf",
        "file_type": "pdf",
        "file_size": 2345678,
        "status": "ready",
        "chunk_count": 45,
        "created_at": "2026-05-20T10:00:00Z"
      }
    ]
  }
}
```

### 20. 删除知识库文件

```
DELETE /kb/files/{file_id}
```

### 21. 知识库问答

```
POST /kb/qa
```

**Request**
```json
{
  "file_ids": [123, 456],
  "query": "React 19 的新特性有哪些？"
}
```

**Response**
```json
{
  "code": 200,
  "data": {
    "answer": "根据文档，React 19 的新特性包括：...",
    "sources": [
      {
        "file_id": 123,
        "filename": "React进阶.pdf",
        "chunk_id": 5,
        "relevance": 0.92
      }
    ]
  }
}
```

## 系统相关 API

### 22. 健康检查

```
GET /health
```

**Response**
```json
{
  "code": 200,
  "data": {
    "status": "healthy",
    "llm_available": true,
    "database_connected": true,
    "version": "1.0.0"
  }
}
```

### 23. 获取模型列表

```
GET /models
```

**Response**
```json
{
  "code": 200,
  "data": {
    "llm_models": [
      {"name": "qwen2.5:7b", "size": "13GB", "available": true},
      {"name": "llama3:8b", "size": "15GB", "available": true}
    ],
    "embedding_models": [
      {"name": "bge-small-zh", "size": "27MB", "available": true}
    ]
  }
}
```

### 24. 保存用户设置

```
PUT /settings
```

**Request**
```json
{
  "theme": "dark",
  "auto_summarize": true,
  "memory_retention_days": 30,
  "search_default_source": "duckduckgo"
}
```

### 25. 导出数据

```
GET /data/export
```

**Response**
```json
{
  "code": 200,
  "data": {
    "download_url": "/api/v1/data/download/export_20260524.json",
    "format": "json",
    "includes": ["messages", "memories", "kb_files"]
  }
}
```

## 错误码

| Code | Message | 说明 |
|------|--------|------|
| 200 | success | 成功 |
| 400 | bad_request | 请求参数错误 |
| 401 | unauthorized | 未授权 |
| 403 | forbidden | 禁止访问 |
| 404 | not_found | 资源不存在 |
| 409 | conflict | 冲突 |
| 429 | too_many_requests | 请求过多 |
| 500 | internal_error | 服务器内部错误 |
| 503 | service_unavailable | 服务不可用 |

## WebSocket API (可选)

### 实时聊天

```
ws://localhost:8000/ws/chat/{session_id}
```

**订阅事件**
```json
{"action": "subscribe", "type": "chat"}
```

**接收事件**
```json
{"type": "message", "content": "...", "role": "assistant"}
{"type": "memory_update", "memories": [...]}
```
