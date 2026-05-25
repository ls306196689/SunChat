# SunChat 技术栈与部署方案

## 核心技术选型

### 1. LLM (大语言模型)

| 模型 | 大小 | 显存需求 | 优势 | 推荐场景 |
|------|------|----------|------|---------|
| Qwen2.5-1.5B | 2.8GB | ~2GB | 超轻量，集成显卡可运行 | 轻量对话、快速响应 |
| Qwen2.5-7B | 13GB | ~8GB | 质量高，速度适中 | 主流配置，通用场景 |
| Qwen2.5-14B | 26GB | ~16GB | 接近 GPT-3.5 质量 | 高质量输出、复杂任务 |
| Llama3-8B | 15GB | ~8GB | 开源最成熟 | 平衡方案 |
| Qwen2.5-32B | 58GB | ~32GB | 接近 GPT-4 质量 | 专业用途、科研 |

**推荐：Qwen2.5-7B** (最佳性价比)

### 2. 嵌入模型

| 模型 | 大小 | 说明 |
|------|------|------|
| bge-small-zh | 27MB | 中文优化，轻量 |
| nomic-embed-text | 50MB | 多语言，通用 |
| mxbai-embed-large | 450MB | 高精度，需更多资源 |

**推荐：bge-small-zh** (中文优化，轻量)

### 3. 向量数据库

| 方案 | 部署复杂度 | 性能 | 适用规模 |
|------|----------|------|---------|
| **Chroma** | 极简 (`pip install`) | 够用 | <100万条 |
| Milvus | 中等 (Docker) | 高 | 亿级 |
| Pinecone | 云服务 | 极高 | 任意 |
| Weaviate | 中等 | 高 | 中大型 |

**推荐：Chroma** (个人项目首选)

### 4. 搜索 API

| API | 免费额度 | 限制 | 推荐指数 |
|-----|---------|------|---------|
| DuckDuckGo (无Key) | 完全免费 | 无速率限制 | ⭐⭐⭐⭐⭐ |
| SearXNG (自建) | 完全免费 | 取决于服务器 | ⭐⭐⭐⭐ |
| Bing Web Search | 1000次/月 | 需 API Key | ⭐⭐⭐ |
| Brave Search | 2000次/月 | 需 API Key | ⭐⭐⭐⭐ |
| Google Custom Search | 100次/天 | 需 API Key | ⭐⭐ |

**推荐方案：DuckDuckGo + SearXNG 组合**

## 本地部署方案

### 方案一：Ollama (最简单)

```bash
# 1. 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. 拉取模型
ollama pull qwen2.5:7b
ollama pull bge-small-zh

# 3. 验证安装
ollama list
ollama run qwen2.5:7b
```

### 方案二：Docker + Ollama

```yaml
# docker-compose.yml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ~/.ollama:/root/.ollama
    restart: unless-stopped

  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - ./chroma_data:/chroma/chroma
    restart: unless-stopped
```

### 方案三：原生安装 (高级用户)

```bash
# 安装 llama.cpp (高性能)
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make

# 下载模型并运行
./main -m models/qwen2.5-7b/ggml-model-q4_k_m.bin \
       -p "你的提示词" \
       -n 512
```

## 完整部署步骤

### 1. 硬件准备

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | i5/Ryzen 5 | i7/Ryzen 7 |
| RAM | 16GB | 32GB+ |
| GPU | 无/集成显卡 | RTX 3060 8GB |
| 存储 | 50GB SSD | 100GB+ SSD |

### 2. 环境安装

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 3.10+
sudo apt install python3 python3-pip python3-venv -y

# 安装 Docker (可选)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

### 3. 项目部署

```bash
# 克隆项目
git clone https://github.com/your-org/sunchat.git
cd sunchat

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install
```

### 4. 配置环境变量

```bash
# 后端 .env
# 模型 API 地址 (Ollama 默认)
LLM_API_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b

# 嵌入模型 API
EMBEDDING_API_URL=http://localhost:11434
EMBEDDING_MODEL=bge-small-zh

# 数据库配置
DATABASE_URL=sqlite:///./data/sunchat.db
CHROMA_PERSIST_DIR=./data/chroma

# 搜索 API (可选，免费方案无需配置)
# SEARCH_API_KEY=

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true
```

### 5. 启动服务

```bash
# 启动后端
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 启动前端 (新终端)
cd frontend
npm run dev
```

## 性能优化建议

### 1. 模型量化

| 量化级别 | 大小 | 显存 | 质量损失 |
|---------|------|------|---------|
| fp16 | 原始 | 原始 | 无 |
| q8_0 | ~50% | ~50% | 极小 |
| q6_K | ~40% | ~40% | 很小 |
| q5_K_M | ~35% | ~35% | 小 |
| q4_K_M | ~25% | ~25% | 中等 |

**推荐：q4_K_M** (平衡质量与性能)

### 2. GPU 内存优化

```bash
# Ollama 启动时指定 GPU
ollama serve --num-gpu 1

# 或设置环境变量
export OLLAMA_NUM_GPU=1
export OLLAMA_MAX_LOADED_MODELS=1
```

### 3. 缓存策略

- 对话缓存：Redis (可选)
- 搜索结果：本地缓存 24 小时
- 嵌入向量：计算后持久化

## 成本估算

### 硬件成本 (一次性)

| 配置 | 预估价格 |
|------|---------|
| 基础 (i5/16GB/集成显卡) | ¥3000-4000 |
| 主流 (i7/32GB/RTX 3060) | ¥6000-8000 |
| 高端 (Ryzen 7/64GB/RTX 4080) | ¥10000+ |

### 运行成本 (每月)

| 项目 | 费用 |
|------|------|
| 电费 (7×24运行) | ¥15-30 |
| 网络 | ¥0 (已有) |
| 其他 | ¥0 |

### 免费方案总结

- **LLM**: Ollama 本地运行 (0元)
- **嵌入**: bge-small-zh 本地运行 (0元)
- **向量库**: Chroma 本地运行 (0元)
- **搜索**: DuckDuckGo 免费 API (0元)
- **总成本**: 0元 (除硬件一次性投入)

## 监控与维护

### 监控指标

- 模型加载状态: `curl http://localhost:11434/api/tags`
- API 响应时间: `curl -w "%{time_total}s" http://localhost:8000/health`
- 数据库大小: `ls -lh data/`

### 备份策略

```bash
# 每日备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf sunchat_backup_$DATE.tar.gz data/
scp sunchat_backup_$DATE.tar.gz user@backup-server:/backup/
rm sunchat_backup_$DATE.tar.gz
```
