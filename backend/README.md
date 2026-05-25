# SunChat Backend

本地 AI 助手后端服务

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/init_db.py

# 测试 LLM 连接
python scripts/test_llm.py

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 配置

复制 `.env.example` 到 `.env` 并根据需要修改：

```bash
cp .env.example .env
```

## API 文档

启动服务后访问: `http://localhost:8000/docs`
