# SunChat - 快速开始

本项目使用本地部署的 Ollama 大模型。

## 前置条件

- 已安装并运行 Ollama
- 已下载 Qwen2.5-7B 模型
- Python 3.10+
- Node.js 18+

## 快速启动

### 1. 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/init_db.py

# 测试 LLM 连接
python scripts/test_llm.py

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 `http://localhost:3000`

## 验证安装

运行 `scripts/test_llm.py`，应该看到：

```
✓ LLM 服务可用
✓ 嵌入模型可用
✓ 搜索服务可用
```

## 项目结构

```
SunChat/
├── backend/          # 后端服务
│   ├── app/         # FastAPI 应用
│   ├── core/        # 核心逻辑
│   ├── services/    # 业务服务
│   ├── models/      # 数据模型
│   ├── api/         # API 路由
│   └── scripts/     # 脚本工具
├── frontend/        # 前端应用
│   └── src/
│       ├── pages/   # 页面组件
│       ├── stores/  # 状态管理
│       └── lib/     # 工具库
└── docs/            # 文档
```

## API 文档

后端启动后访问: `http://localhost:8000/docs`
