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

REM Get current directory (Windows path)
set "WIN_PATH=%~dp0"
set "WIN_PATH=%WIN_PATH:~0,-1%"

REM Convert Windows path to WSL path
REM Extract drive letter (first character)
set "DRIVE_LETTER=%WIN_PATH:~0,1%"
set "PATH_AFTER_DRIVE=%WIN_PATH:~3%"

REM Convert backslashes to forward slashes
set "PATH_AFTER_DRIVE=%PATH_AFTER_DRIVE:\=/%"

REM Build WSL path based on drive letter
if /i "%DRIVE_LETTER%"=="C" set "WSL_PATH=/mnt/c%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="D" set "WSL_PATH=/mnt/d%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="E" set "WSL_PATH=/mnt/e%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="F" set "WSL_PATH=/mnt/f%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="G" set "WSL_PATH=/mnt/g%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="H" set "WSL_PATH=/mnt/h%PATH_AFTER_DRIVE%"

REM Check if conversion was successful
if "%WSL_PATH%"=="" (
    echo [ERROR] Could not convert Windows path to WSL path.
    echo Windows path: %WIN_PATH%
    echo Drive letter: %DRIVE_LETTER%
    echo Please ensure the repository is on a supported drive (C: through H:)
    pause
    exit /b 1
)

REM Debug output
echo [INFO] Windows path: %WIN_PATH%
echo [INFO] WSL path: %WSL_PATH%
echo.

REM Test if the path exists in WSL
echo [INFO] Testing if path exists in WSL...
wsl test -d "%WSL_PATH%" 2>nul
if errorlevel 1 (
    echo [ERROR] Path does not exist in WSL: %WSL_PATH%
    echo Please verify the path conversion is correct.
    pause
    exit /b 1
)
echo [OK] Path exists in WSL
echo.

REM Test if start.sh exists
echo [INFO] Testing if start.sh exists...
wsl test -f "%WSL_PATH%/start.sh" 2>nul
if errorlevel 1 (
    echo [ERROR] start.sh not found at: %WSL_PATH%/start.sh
    pause
    exit /b 1
)
echo [OK] start.sh found
echo.

REM Launch start.sh in WSL
echo [INFO] Launching start.sh in WSL...
echo.
wsl bash -c "cd '%WSL_PATH%' && chmod +x start.sh && bash start.sh"

REM Check exit code (must check immediately after command)
if errorlevel 1 (
    echo.
    echo [ERROR] start.sh failed to execute.
    echo Check the error messages above for details.
    pause
    exit /b 1
)
