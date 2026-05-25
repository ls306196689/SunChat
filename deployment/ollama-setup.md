# SunChat 本地大模型部署指南

## 第一步：硬件检查

### 最低配置
- CPU: 双核 2.0GHz+
- RAM: 8GB+
- 存储: 30GB 可用空间

### 推荐配置
- CPU: i5/Ryzen 5 或更好
- RAM: 16GB+
- GPU: RTX 3060 8GB 或更好
- 存储: 100GB SSD+

### 检查命令
```bash
# CPU 信息
lscpu | grep "Model name"

# 内存信息
free -h

# 磁盘空间
df -h /

# GPU 信息 (NVIDIA)
nvidia-smi

# GPU 信息 (AMD)
lspci | grep -i vga
```

## 第二步：安装 Ollama

Ollama 是最简单的本地大模型部署方案。

### Linux 安装
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 验证安装
```bash
ollama --version
# 输出: ollama version is x.x.x
```

### 启动 Ollama 服务
```bash
# 系统服务方式 (推荐)
sudo systemctl start ollama
sudo systemctl enable ollama

# 手动启动
ollama serve
```

## 第三步：下载模型

### 推荐模型列表

| 模型 | 大小 | 显存 | 适合场景 |
|------|------|------|---------|
| qwen2.5:1.5b | 2.8GB | ~2GB | 轻量对话，低配机器 |
| qwen2.5:7b | 13GB | ~8GB | 主流配置，平衡方案 |
| qwen2.5:14b | 26GB | ~16GB | 高质量输出 |
| llama3:8b | 15GB | ~8GB | 开源最成熟 |
| qwen2.5:32b | 58GB | ~32GB | 专业用途 |

### 下载命令
```bash
# 下载 Qwen2.5-7B (推荐)
ollama pull qwen2.5:7b

# 下载嵌入模型
ollama pull nomic-embed-text

# 下载 Llama3-8B (备选)
ollama pull llama3:8b

# 查看已下载模型
ollama list
```

### 下载进度监控
```bash
# 查看当前运行状态
ollama ps

# 查看服务日志
tail -f ~/.ollama/logs/ollama.log
```

## 第四步：配置环境变量

### 创建 `.env` 文件

```bash
cd /home/user/Documents/SunChat/backend
cp .env.example .env
```

### `.env` 内容
```bash
# Ollama API 配置
LLM_API_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b

# 嵌入模型配置
EMBEDDING_API_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text

# 数据库配置
DATABASE_URL=sqlite:///./data/sunchat.db
CHROMA_PERSIST_DIR=./data/chroma

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true

# 搜索配置 (可选)
# SEARCH_API_KEY=
```

## 第五步：测试模型

### 测试 LLM
```bash
# 使用 ollama 命令测试
ollama run qwen2.5:7b

# 输入测试
>>> 你好，请介绍 yourself
>>> 1+1 等于几
```

### 测试嵌入模型
```python
import requests

# 测试嵌入 API
response = requests.post(
    "http://localhost:11434/api/embeddings",
    json={
        "model": "nomic-embed-text",
        "prompt": "测试文本"
    }
)
print(response.json())
```

## 第六步：优化配置

### 1. GPU 加速

```bash
# 检查 CUDA 是否可用
nvidia-smi

# 设置 Ollama 使用 GPU
export OLLAMA_NUM_GPU=1
export OLLAMA_MAX_LOADED_MODELS=1

# 重启 Ollama
sudo systemctl restart ollama
```

### 2. 内存优化

```bash
# 限制模型大小 (Qwen2.5-7B 量化版本)
ollama pull qwen2.5:7b-q4_K_M  # 约 5GB 显存
ollama pull qwen2.5:7b-q5_K_M  # 约 6GB 显存
```

### 3. 网络配置

```bash
# 如果需要远程访问
ollama serve --host 0.0.0.0 --port 11434
```

## 第七步：运行 SunChat

### 启动后端
```bash
cd /home/user/Documents/SunChat/backend

# 创建数据目录
mkdir -p data

# 安装依赖
pip install -r requirements.txt

# 运行服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 启动前端
```bash
cd /home/user/Documents/SunChat/frontend

npm install
npm run dev
```

访问 `http://localhost:3000`

## 常见问题排查

### 1. 模型下载失败
```bash
# 检查网络
ping ollama.com

# 尝试代理
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

### 2. 模型加载失败 (OOM)
```bash
# 使用量化版本
ollama pull qwen2.5:7b-q4_K_M

# 或减小批次大小
ollama run qwen2.5:7b --num_ctx 2048
```

### 3. API 连接失败
```bash
# 检查 Ollama 服务状态
systemctl status ollama

# 测试 API
curl http://localhost:11434/api/tags

# 重启服务
sudo systemctl restart ollama
```

### 4. GPU 不工作
```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 安装 CUDA (如果需要)
# Ubuntu
sudo apt install nvidia-driver-535
sudo reboot
```

## 高级配置

### 使用 Docker 部署 Ollama

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
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### 模型微调 (可选)

```bash
# 使用 llama-fine-tune 进行微调
# 仅适用于高级用户
git clone https://github.com/unslothai/llama-fine-tune
cd llama-fine-tune
# 配置数据集和参数
python fine_tune.py
```

## 性能基准测试

### Qwen2.5-7B (RTX 3060)
- 首Token时间: ~300ms
- 生成速度: ~20 tokens/s
- 显存占用: ~7GB
- 响应质量: ⭐⭐⭐⭐

### Llama3-8B (RTX 3060)
- 首Token时间: ~350ms
- 生成速度: ~18 tokens/s
- 显存占用: ~7GB
- 响应质量: ⭐⭐⭐⭐

## 备份与维护

### 备份模型
```bash
# 模型存储在
ls -la ~/.ollama/models/

# 备份
tar -czf ollama_models_backup.tar.gz ~/.ollama/models/
```

### 清理缓存
```bash
# 清理未使用的模型
ollama prune

# 清理 Ollama 缓存
rm -rf ~/.ollama/cache/*
```
