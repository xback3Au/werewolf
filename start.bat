@echo off
chcp 65001 > nul
echo ===================================
echo   狼人杀实时分析系统启动脚本
echo ===================================
echo.

REM Check if .env exists
if not exist "backend\.env" (
    echo [错误] 找不到 backend\.env 文件
    echo 请创建 backend\.env 文件并添加 DEEPSEEK_API_KEY
    pause
    exit /b 1
)

echo [1/3] 正在启动后端服务...
cd backend
start "后端服务" cmd /k "uvicorn main:app --reload --port 8000"
cd ..

timeout /t 3 /nobreak > nul

echo [2/3] 正在启动前端服务...
cd frontend
start "前端服务" cmd /k "npm run dev"
cd ..

timeout /t 5 /nobreak > nul

echo.
echo ===================================
echo   服务启动完成！
echo ===================================
echo 后端API: http://localhost:8000
echo 前端界面: http://localhost:5173
echo API文档: http://localhost:8000/docs
echo.
pause
