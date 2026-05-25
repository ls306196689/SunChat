# SunChat Backend - Directory Structure

backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置加载
│   └── dependencies.py            # 依赖注入
│
├── core/
│   ├── __init__.py
│   ├── llm.py                     # LLM 服务封装 (Ollama)
│   ├── embedding.py               # 嵌入模型服务
│   ├── search.py                  # 搜索服务
│   └── security.py                # 安全相关工具
│
├── services/
│   ├── __init__.py
│   ├── chat_service.py            # 聊天服务
│   ├── memory_service.py          # 记忆服务
│   ├── knowledge_service.py       # 知识库服务
│   └── search_service.py          # 搜索服务
│
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py            # 认证路由
│   │   │   ├── chat.py            # 聊天路由
│   │   │   ├── memories.py        # 记忆路由
│   │   │   ├── search.py          # 搜索路由
│   │   │   ├── knowledge.py       # 知识库路由
│   │   │   └── health.py          # 健康检查路由
│   │   └── deps.py                # API 依赖
│   └── dependencies.py            # 全局依赖
│
├── models/
│   ├── __init__.py
│   ├── database.py                # 数据库连接
│   ├── schemas.py                 # Pydantic 模型
│   └── sql_models.py              # SQLAlchemy 模型
│
├── utils/
│   ├── __init__.py
│   ├── memory_extractor.py        # 记忆提取器
│   ├── search_router.py           # 搜索意图路由
│   └── exceptions.py              # 自定义异常
│
├── data/
│   ├── __init__.py
│   ├── sunchat.db                 # SQLite 数据库 (自动生成)
│   └── chroma/                    # Chroma 向量库 (自动生成)
│
├── scripts/
│   ├── __init__.py
│   ├── init_db.py                 # 初始化数据库
│   └── test_llm.py                # 测试 LLM 连接
│
├── .env                           # 环境变量
├── .env.example                   # 环境变量示例
├── requirements.txt
└── README.md
```
