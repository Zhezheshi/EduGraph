#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "=== EduGraph Agent ==="

# 后端
echo "[1/2] 启动后端..."
cd src
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 前端
echo "[2/2] 启动前端..."
cd src/frontend
npm run dev &
FRONTEND_PID=$!
cd ../..

echo ""
echo "后端: http://localhost:8000"
echo "前端: http://localhost:3000"
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
