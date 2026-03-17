#!/bin/bash
set -e

# AI评委系统 一键启动脚本
# Usage: ./start.sh [dev|docker]

MODE="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

check_env() {
  if [ ! -f "$ROOT_DIR/backend/.env" ]; then
    warn "未找到 backend/.env，正在从 .env.example 复制..."
    cp "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
    warn "请编辑 backend/.env 填入真实的 API Key 后重新运行"
    exit 1
  fi
}

start_dev() {
  info "=== 开发模式启动 ==="
  check_env

  # 启动后端
  info "启动后端 (FastAPI on :8000)..."
  cd "$ROOT_DIR/backend"
  if ! command -v uv &> /dev/null; then
    error "未安装 uv，请先运行: curl -LsSf https://astral.sh/uv/install.sh | sh"
  fi
  uv sync
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
  BACKEND_PID=$!

  # 启动前端
  info "启动前端 (Vite on :3000)..."
  cd "$ROOT_DIR/frontend"
  if ! command -v npm &> /dev/null; then
    error "未安装 npm，请先安装 Node.js"
  fi
  npm install
  npm run dev &
  FRONTEND_PID=$!

  info "=== 启动完成 ==="
  info "前端: http://localhost:3000"
  info "后端: http://localhost:8000"
  info "API文档: http://localhost:8000/docs"
  echo ""
  info "按 Ctrl+C 停止所有服务"

  trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
  wait
}

start_docker() {
  info "=== Docker 模式启动 ==="
  check_env

  if ! command -v docker &> /dev/null; then
    error "未安装 Docker，请先安装 Docker Desktop"
  fi

  cd "$ROOT_DIR"
  docker compose up --build

  info "前端: http://localhost:3000"
  info "后端: http://localhost:8000"
}

case "$MODE" in
  dev)    start_dev ;;
  docker) start_docker ;;
  *)      echo "Usage: $0 [dev|docker]"; exit 1 ;;
esac
