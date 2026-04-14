@echo off
:: Compound Wiki 快捷启动脚本 (Windows)
:: 使用方法: cw.bat <命令>

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0.."
set "PYTHON_SCRIPT=%SCRIPT_DIR%\scripts\cw_tool.py"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 需要 Python 环境
    echo 请先安装 Python: https://python.org
    exit /b 1
)

python "%PYTHON_SCRIPT%" %*
