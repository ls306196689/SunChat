#!/usr/bin/env bash
# --------------------------------------------------------
# 项目根目录的启动脚本
# 作用：一键启动后端 (FastAPI) + 前端 (Vite)
# --------------------------------------------------------

set -e               # 任何命令失败即退出
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# ---------- 1️⃣ 统一退出处理 ----------
cleanup() {
  echo -e "\n▶️ 正在停止服务..."
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null && echo "   • 后端已停止 (PID=$BACKEND_PID)"
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null && echo "   • 前端已停止 (PID=$FRONTEND_PID)"
  exit 0
}
trap cleanup SIGINT SIGTERM

# ---------- 2️⃣ 启动后端 ----------
echo "▶️ 启动后端 (FastAPI)..."
cd "$SCRIPT_DIR/backend"

# 如已创建虚拟环境则自动激活
if [ -d "venv" ]; then
  echo "   • 使用已有 virtualenv"
  source venv/bin/activate
else
  echo "   • 未检测到 virtualenv，使用系统 Python"
fi

# 安装依赖（仅在缺失时执行）
if [ ! -f "requirements.txt" ] || ! pip freeze | grep -q "fastapi"; then
  echo "   • 安装后端依赖..."
  pip install -r requirements.txt
fi

# 启动 uvicorn（后台 & 保存 PID）
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  > backend.log 2>&1 &
BACKEND_PID=$!
echo "   • 后端已启动 (PID=$BACKEND_PID) → http://localhost:8000"

# ---------- 3️⃣ 启动前端 ----------
echo "▶️ 启动前端 (Vite)..."
cd "$SCRIPT_DIR/frontend"

# 安装前端依赖（仅在 node_modules 不存在时执行）
if [ ! -d "node_modules" ]; then
  echo "   • 安装前端依赖..."
  npm install
fi

# 启动 Vite dev server（后台 & 保存 PID）
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   • 前端已启动 (PID=$FRONTEND_PID) → http://localhost:5173"

# ---------- 4️⃣ 监听子进程 ----------
echo -e "\n✅ 所有服务已启动，按 Ctrl+C 可一键停止。\n"

# 等待任意子进程退出（若其中一个意外退出，直接结束另一个）
wait -n
cleanup   # 若有进程提前结束，执行清理
