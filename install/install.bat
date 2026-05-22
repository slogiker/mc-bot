@echo off
setlocal EnableDelayedExpansion
title MC-Bot Installer (Windows)

:: ANSI Color Codes
for /F %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"
set "CYAN=%ESC%[36m"
set "GREEN=%ESC%[32m"
set "YELLOW=%ESC%[33m"
set "RED=%ESC%[31m"
set "NC=%ESC%[0m"

:: Enable ANSI/VT100 support
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

echo.
echo %CYAN%=========================================================%NC%
echo %CYAN%     Minecraft Discord Bot - Windows Installer           %NC%
echo %CYAN%=========================================================%NC%
echo.

:: Check for Administrative privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[ERROR] This installer requires Administrative privileges.%NC%
    echo %YELLOW%Please right-click install.bat and select "Run as administrator".%NC%
    echo.
    pause
    exit /b 1
)

echo %GREEN%[OK] Administrative privileges confirmed.%NC%
echo.

:: Launch PowerShell logic
powershell.exe -ExecutionPolicy Bypass -File "%~dp0install.ps1"

if %errorLevel% neq 0 (
    echo.
    echo %RED%[ERROR] Installation failed or was cancelled.%NC%
    pause
    exit /b %errorLevel%
)

exit /b 0
