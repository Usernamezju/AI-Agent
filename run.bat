@echo off
REM =============================================================================
REM AI Agent Framework — one-click launcher (Windows)
REM
REM Usage:
REM   run.bat            → Streamlit Web UI (default)
REM   run.bat cli        → CLI interactive mode
REM   run.bat install    → Only install dependencies, don't launch
REM =============================================================================
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =============================================
echo   AI Agent Framework — ReAct
echo =============================================
echo.

REM ---- Python check ----
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] python not found. Install Python ≥3.10 first.
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] %%i

REM ---- .env check ----
if not exist ".env" (
    echo [!] .env not found — creating from template.
    (
        echo DEEPSEEK_API_KEY=sk-your-key-here
        echo SANDBOX_ROOT=./sandbox
    ) > .env
    echo     Edit .env and paste your DeepSeek API key, then re-run.
    pause
    exit /b 0
)

findstr /c:"sk-your-key-here" .env >nul 2>&1
if !errorlevel! equ 0 (
    echo [!] You still have the placeholder API key in .env.
    echo     Edit .env and use a real key from https://platform.deepseek.com
)

REM ---- dependencies ----
set MODE=%1
if "%MODE%"=="" set MODE=web

echo.
echo [*] Installing dependencies ...
python -m pip install -q -r requirements.txt 2>&1 | findstr /v "already satisfied" >nul
echo [OK] Dependencies ready.

if "%MODE%"=="install" (
    echo.
    echo Dependencies installed. Run run.bat to start.
    pause
    exit /b 0
)

REM ---- launch ----
echo.
if "%MODE%"=="cli" (
    echo [*] Starting CLI mode ...
    python scripts\run_agent.py
) else (
    echo [*] Starting Web UI ...
    echo     Open http://localhost:8501 in your browser
    echo.
    streamlit run ui\app.py --server.headless true
)
pause
