@echo off
REM =============================================================================
REM AI Agent Framework — Package as standalone .exe (Windows)
REM =============================================================================
chcp 65001 >nul
cd /d "%~dp0"

echo =============================================
echo   Packaging AI Agent Framework into .exe
echo =============================================
echo.

REM ---- Check PyInstaller ----
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing PyInstaller...
    pip install pyinstaller
    echo.
)

REM ---- Clean previous build ----
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [*] Building .exe (this may take 2-5 minutes)...
echo.

REM ---- PyInstaller build (only core, no demos/tests/docs/sandbox) ----
pyinstaller --noconfirm --clean ^
    --name "AI-Agent" ^
    --add-data "src;src" ^
    --add-data "config;config" ^
    --add-data "ui;ui" ^
    --add-data "prompts;prompts" ^
    --add-data ".chainlit;.chainlit" ^
    --add-data "chainlit.md;." ^
    --exclude-module tests ^
    --exclude-module experiments ^
    --exclude-module scripts ^
    --hidden-import streamlit ^
    --hidden-import chainlit ^
    --hidden-import openai ^
    --hidden-import dotenv ^
    --hidden-import yaml ^
    --collect-all streamlit ^
    --collect-all chainlit ^
    launcher.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. Try running: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo =============================================
echo   Build complete!
echo   Output: dist\AI-Agent\AI-Agent.exe
echo =============================================
echo.
echo To run: double-click dist\AI-Agent\AI-Agent.exe
echo Or from terminal: dist\AI-Agent\AI-Agent.exe
echo.
pause
