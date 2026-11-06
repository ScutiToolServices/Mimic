@echo off
REM LABEL: Mimic Service
REM DESCRIPTION: Consented voice-cloning MCP server for Citadel and Ember, port 8094.
cd /d "%~dp0"
set "UV_CACHE_DIR=D:/User/.uv-cache"
uv sync
if errorlevel 1 (
    echo uv sync failed. Install uv: winget install astral-sh.uv
    pause
    exit /b 1
)
uv run python -m src.run
pause
