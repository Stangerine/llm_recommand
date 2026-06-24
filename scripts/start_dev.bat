@echo off
REM 快速启动开发环境（Windows 版）

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

echo ==========================================
echo 推荐系统 - 开发环境启动
echo ==========================================

REM 1. 验证数据
echo.
echo Step 1: 验证数据文件...
python "%SCRIPT_DIR%validate_data.py"
if errorlevel 1 (
    echo 数据验证失败，请检查数据文件
    exit /b 1
)

REM 2. 检查后端依赖
echo.
echo Step 2: 检查后端依赖...
cd /d "%PROJECT_ROOT%\backend"
if not exist ".venv" (
    echo 创建 Python 虚拟环境...
    python -m venv .venv
)

echo 激活虚拟环境并安装依赖...
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

REM 3. 检查前端依赖
echo.
echo Step 3: 检查前端依赖...
cd /d "%PROJECT_ROOT%\frontend"
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
)

REM 4. 启动服务
echo.
echo Step 4: 启动服务...
echo.

REM 启动后端
echo 启动后端服务 (端口 8000)...
cd /d "%PROJECT_ROOT%\backend"
start "Backend" cmd /c "call .venv\Scripts\activate.bat && uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端
echo 启动前端服务 (端口 5173)...
cd /d "%PROJECT_ROOT%\frontend"
start "Frontend" cmd /c "npm run dev"

echo.
echo ==========================================
echo 服务已启动！
echo ==========================================
echo.
echo 前端: http://localhost:5173
echo 后端 API: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo 健康检查: http://localhost:8000/health
echo 系统指标: http://localhost:8000/metrics
echo.
echo 关闭窗口停止服务
echo.
pause
