@echo off
echo ========================================
echo    安巡 - 校园网络风险感知智能体
echo ========================================
echo.
echo 正在启动应用...
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

:: 检查是否安装了依赖
echo 检查依赖包...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

:: 启动应用
echo.
echo 启动Streamlit应用...
echo 应用将在浏览器中自动打开: http://localhost:8501
echo.
echo 按Ctrl+C停止应用
echo.

streamlit run app.py

pause