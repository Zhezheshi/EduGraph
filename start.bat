@echo off
echo === EduGraph Agent ===

echo [1/2] 启动后端...
start "EduGraph Backend" cmd /c "cd src && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

echo [2/2] 启动前端...
start "EduGraph Frontend" cmd /c "cd src\frontend && npm run dev"

echo.
echo 后端: http://localhost:8000
echo 前端: http://localhost:3000
echo.
pause
