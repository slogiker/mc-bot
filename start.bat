@echo off
setlocal enabledelayedexpansion

REM Minecraft Discord Bot - Windows Startup Script (WSL Launcher)
echo [INFO] Starting Minecraft Discord Bot launcher...
echo.

REM Check if WSL is available
echo [INFO] Checking for WSL...
where wsl >nul 2>&1
if errorlevel 1 (
    echo [ERROR] WSL is not installed or not in PATH.
    echo Please install WSL: https://aka.ms/wsl
    pause
    exit /b 1
)
echo [OK] WSL found
echo.

REM Get current directory (Windows path)
set "WIN_PATH=%~dp0"
set "WIN_PATH=%WIN_PATH:~0,-1%"
echo [INFO] Current directory: %WIN_PATH%
echo.

REM Convert Windows path to WSL path
REM Extract drive letter (first character)
set "DRIVE_LETTER=%WIN_PATH:~0,1%"
set "PATH_AFTER_DRIVE=%WIN_PATH:~3%"

echo [DEBUG] Drive letter: %DRIVE_LETTER%
echo [DEBUG] Path after drive: %PATH_AFTER_DRIVE%

REM Convert backslashes to forward slashes
set "PATH_AFTER_DRIVE=%PATH_AFTER_DRIVE:\=/%"

REM Build WSL path based on drive letter
set "WSL_PATH="
if /i "%DRIVE_LETTER%"=="C" set "WSL_PATH=/mnt/c%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="D" set "WSL_PATH=/mnt/d%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="E" set "WSL_PATH=/mnt/e%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="F" set "WSL_PATH=/mnt/f%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="G" set "WSL_PATH=/mnt/g%PATH_AFTER_DRIVE%"
if /i "%DRIVE_LETTER%"=="H" set "WSL_PATH=/mnt/h%PATH_AFTER_DRIVE%"

REM Check if conversion was successful
if "!WSL_PATH!"=="" (
    echo [ERROR] Could not convert Windows path to WSL path.
    echo Windows path: %WIN_PATH%
    echo Drive letter: %DRIVE_LETTER%
    echo Path after drive: %PATH_AFTER_DRIVE%
    echo Please ensure the repository is on a supported drive (C: through H:)
    pause
    exit /b 1
)

echo [INFO] WSL path: !WSL_PATH!
echo.

REM Test if the path exists in WSL
echo [INFO] Testing if path exists in WSL...
wsl test -d "!WSL_PATH!" 2>&1
if errorlevel 1 (
    echo [ERROR] Path does not exist in WSL: !WSL_PATH!
    echo Please verify the path conversion is correct.
    pause
    exit /b 1
)
echo [OK] Path exists in WSL
echo.

REM Test if start.sh exists
echo [INFO] Testing if start.sh exists...
wsl test -f "!WSL_PATH!/start.sh" 2>&1
if errorlevel 1 (
    echo [ERROR] start.sh not found at: !WSL_PATH!/start.sh
    pause
    exit /b 1
)
echo [OK] start.sh found
echo.

REM Launch start.sh in WSL
echo [INFO] Launching start.sh in WSL...
echo ========================================
echo.

wsl bash -c "cd '!WSL_PATH!' && chmod +x start.sh && bash start.sh"

REM Check exit code
if errorlevel 1 (
    echo.
    echo ========================================
    echo [ERROR] start.sh failed to execute.
    echo Check the error messages above for details.
    pause
    exit /b 1
)

endlocal
