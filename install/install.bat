@echo off
setlocal EnableDelayedExpansion

REM Minecraft Discord Bot - Windows Installer & Bootstrapper
REM Forces WSL (Ubuntu) installation and hands off to Linux script.

:check_admin
NET SESSION >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Requesting Administrator privileges...
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

echo [INFO] Running with Administrator privileges.

:check_wsl
wsl --status >nul 2>&1
if %errorLevel% neq 0 (
    goto :install_wsl
)

REM Check if Ubuntu is installed
wsl --list | findstr "Ubuntu" >nul
if %errorLevel% neq 0 (
    echo [WARN] WSL is active but Ubuntu is missing.
    goto :install_ubuntu
)

goto :launch_wsl

:install_wsl
echo [WARN] WSL is not installed or enabled.
echo [INFO] Installing WSL (Ubuntu)... System REBOOT required.
echo.
echo [IMPORTANT] The system will restart automatically after installation.
echo [IMPORTANT] This script will resume automatically after you log back in.
echo.
pause

REM Set RunOnce registry key for persistence
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce" /v "MCBotInstall" /t REG_SZ /d "\"%~f0\"" /f >nul

REM Install WSL and Ubuntu
wsl --install -d Ubuntu

if %errorLevel% neq 0 (
    echo [ERROR] WSL installation failed!
    pause
    exit /b 1
)

echo [INFO] Rebooting system in 5 seconds...
shutdown /r /t 5
pause
exit /b

:install_ubuntu
echo [INFO] Installing Ubuntu distro...
wsl --install -d Ubuntu
if %errorLevel% neq 0 (
    echo [ERROR] Ubuntu installation failed!
    pause
    exit /b 1
)
echo [SUCCESS] Ubuntu installed.
goto :launch_wsl

:launch_wsl
echo [INFO] Environment ready. Launching Linux setup...
echo.

REM Convert current path directly to WSL path
REM Using a temporary powershell command to get wslpath is reliable
for /f "delims=" %%i in ('wsl wslpath -u "%~dp0.."') do set "PROJECT_ROOT=%%i"

REM Execute install.sh inside WSL
REM Ensure line endings are fixed just in case
wsl -d Ubuntu -u root -- bash -c "cd '%PROJECT_ROOT%' && tr -d '\r' < install/install.sh > install/install_run.sh && chmod +x install/install_run.sh && ./install/install_run.sh"

if %errorLevel% neq 0 (
    echo [ERROR] Linux installation script failed.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Installation complete!
pause
