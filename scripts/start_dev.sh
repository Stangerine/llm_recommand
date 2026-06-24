#!/bin/bash
# 快速启动开发环境（使用真实数据）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "推荐系统 - 开发环境启动"
echo "=========================================="

# 1. 验证数据
echo ""
echo "Step 1: 验证数据文件..."
python "$SCRIPT_DIR/validate_data.py"
if [ $? -ne 0 ]; then
    echo "数据验证失败，请检查数据文件"
    exit 1
fi

# 2. 检查后端依赖
echo ""
echo "Step 2: 检查后端依赖..."
cd "$PROJECT_ROOT/backend"
if [ ! -d ".venv" ]; then
    echo "创建 Python 虚拟环境..."
    python -m venv .venv
fi

echo "激活虚拟环境并安装依赖..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi
pip install -q -r requirements.txt

# 3. 检查前端依赖
echo ""
echo "Step 3: 检查前端依赖..."
cd "$PROJECT_ROOT/frontend"
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 4. 启动服务
echo ""
echo "Step 4: 启动服务..."
echo ""

# 启动后端
echo "启动后端服务 (端口 8000)..."
cd "$PROJECT_ROOT/backend"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动前端
echo "启动前端服务 (端口 5173)..."
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "服务已启动！"
echo "=========================================="
echo ""
echo "前端: http://localhost:5173"
echo "后端 API: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
echo "健康检查: http://localhost:8000/health"
echo "系统指标: http://localhost:8000/metrics"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 等待用户中断
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
