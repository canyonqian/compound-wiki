@echo off
REM ============================================
REM  CAM — Auto Agent Launcher
REM  Windows
REM ====================================

setlocal

set "CAM_DIR=%~dp0"
cd /d "%CAM_DIR%"

echo ============================================
echo   CAM — Auto Agent
echo   Starting intelligent memory system...
echo ============================================.
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist "%CAM_DIR%\.installed" (
    echo [SETUP] Installing required packages...
    pip install watchdog anthropic openai --quiet 2>nul
    type nul > "%CAM_DIR%\.installed"
    echo [OK] Dependencies installed.
    echo.
)

REM Run agent with provided arguments, default to 'start'
if "%~1"=="" (
    python auto\agent.py start
) else (
    python auto\agent.py %*
)
