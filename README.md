# SunChat - 个人智能聊天系统

**你的记忆，你的助手，永远免费**

SunChat 是一个本地优先的个人 AI 助手系统，具备记忆、知识库和多领域问题解决能力。所有敏感数据本地存储，可选端到端加密同步。

## 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 三层记忆 | 短期(对话缓存) + 中期(事件) + 长期(知识/偏好) |
| 📚 个人知识库 | RAG 架构，支持 PDF/Word/网页/语音笔记 |
| 🔍 智能搜索 | 免费搜索 API 聚合，意图路由，结果融合验证 |
| 🏠 本地优先 | LLM + 向量数据库全本地运行 |
| 🔒 隐私保护 | AES-256-GCM 加密，端到端加密同步 |
| 🎨 多端支持 | Web / 桌面(Tauri) / 移动端(Flutter) |

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- Docker (可选，用于数据库)
- GPU 显存 ≥ 8GB (本地运行 Qwen2.5-7B/Llama3-8B)

### 本地部署

```bash
# 1. 安装 Ollama 并拉取模型
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# 2. 克隆并安装后端
cd backend
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn main:app --reload

# 3. 运行前端
cd ../frontend
npm install
npm run dev
```

访问 `http://localhost:3000` 开始使用。

## 项目结构

```
SunChat/
├── docs/                    # 需求与设计文档
│   ├── feat.md             # 核心功能需求
│   ├── websearch+memory.md # 搜索与记忆模块设计
│   └── add.md              # 补充设计响应
├── architecture/            # 系统架构文档
│   ├── overview.md         # 架构概览
│   ├── data-flow.md        # 数据流设计
│   └── security.md         # 安全架构
├── backend/                 # 后端服务
│   ├── app/                # 主应用
│   ├── core/               # 核心逻辑
│   ├── models/             # 数据模型
│   ├── services/           # 业务服务
│   └── api/                # API 路由
├── frontend/                # 前端应用
│   ├── src/
│   │   ├── components/     # UI 组件
│   │   ├── pages/          # 页面
│   │   ├── stores/         # 状态管理
│   │   └── lib/            # 工具库
│   └── package.json
├── deployment/              # 部署配置
│   ├── docker-compose.yml
│   ├── ollama-setup.sh
│   └── backup-script.sh
└── README.md
```

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM | Qwen2.5 / Llama3 (本地 Ollama) |
| 嵌入模型 | bge-small-zh / nomic-embed-text |
| 向量数据库 | Chroma |
| 后端 | Python + FastAPI |
| 前端 | React + TypeScript + Tauri |
| 数据库 | SQLite + PostgreSQL (可选) |
| 搜索 | DuckDuckGo API + SearXNG |

## 功能迭代路线

- **Phase 1 (MVP)**: 基础对话 + 聊天记录 + 简单记忆
- **Phase 2**: 个人知识库 + 文档上传问答
- **Phase 3**: 多 Agent (日程、搜索、编程)
- **Phase 4**: 情感记忆 + 主动提醒
- **Phase 5**: 跨设备同步 + 语音交互

## 社区与支持

- [Issue Tracker](https://github.com/your-org/sunchat/issues)
- [文档](https://docs.sunchat.ai)
- [Discord](https://discord.gg/sunchat)

## 许可证

MIT License
