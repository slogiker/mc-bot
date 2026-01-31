@echo off
REM Minecraft Discord Bot - Windows Startup Script (WSL Launcher)
REM This script launches start.sh in WSL for Windows users

REM Check if WSL is available
where wsl >nul 2>&1
if errorlevel 1 (
    echo [ERROR] WSL is not installed or not in PATH.
    echo Please install WSL: https://aka.ms/wsl
    pause
    exit /b 1
)

REM Get current directory and convert to WSL path
set "WIN_PATH=%~dp0"
set "WIN_PATH=%WIN_PATH:~0,-1%"
set "WIN_PATH=%WIN_PATH:\=/%"

REM Convert drive letter to WSL mount point (C: -> /mnt/c, D: -> /mnt/d, etc.)
if "%WIN_PATH:~0,2%"=="C:" set "WIN_PATH=/mnt/c%WIN_PATH:~2%"
if "%WIN_PATH:~0,2%"=="D:" set "WIN_PATH=/mnt/d%WIN_PATH:~2%"
if "%WIN_PATH:~0,2%"=="E:" set "WIN_PATH=/mnt/e%WIN_PATH:~2%"
if "%WIN_PATH:~0,2%"=="F:" set "WIN_PATH=/mnt/f%WIN_PATH:~2%"

REM Check if we successfully converted a known drive
echo %WIN_PATH% | findstr /R "^/mnt/[a-z]/" >nul
if errorlevel 1 (
    echo [ERROR] Could not convert Windows path to WSL path.
    echo Current path: %WIN_PATH%
    echo Please ensure the repository is on drive C:, D:, E:, or F:
    pause
    exit /b 1
)

REM Launch start.sh in WSL
wsl bash -c "cd '%WIN_PATH%' && chmod +x start.sh && ./start.sh"

REM Keep window open if there was an error
if errorlevel 1 pause
