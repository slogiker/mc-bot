@echo off
setlocal EnableDelayedExpansion
title MC-Bot Installer (WSL + Docker)

:: ANSI Color Codes (Windows 10+ with VT100 enabled)
for /F %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"
set "CYAN=%ESC%[36m"
set "GREEN=%ESC%[32m"
set "YELLOW=%ESC%[33m"
set "BLUE=%ESC%[34m"
set "RED=%ESC%[31m"
set "NC=%ESC%[0m"

:: Enable ANSI/VT100 support
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

:: Check for Admin Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[WARN] Administrator privileges required for WSL installation%NC%
    echo %BLUE%[INFO] Requesting administrator access...%NC%
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

echo %CYAN%╔════════════════════════════════════════════════════════════════╗%NC%
echo %CYAN%║                                                                ║%NC%
echo %CYAN%║        Minecraft Discord Bot - Windows Installer (WSL)        ║%NC%
echo %CYAN%║                                                                ║%NC%
echo %CYAN%╚════════════════════════════════════════════════════════════════╝%NC%
echo.

:: Registry RunOnce Path for post-reboot continuation
set "REG_PATH=HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce"
set "REG_KEY=MCBotInstall"

:: Check if this is a resume after reboot
reg query "%REG_PATH%" /v "%REG_KEY%" >nul 2>&1
if %errorlevel% equ 0 (
    echo %BLUE%[RESUME] Detected resume after restart. Cleaning up registry...%NC%
    reg delete "%REG_PATH%" /v "%REG_KEY%" /f >nul
    echo %BLUE%[RESUME] Continuing installation...%NC%
    goto :RunSetup
)

:: Check WSL Status
echo %BLUE%[STEP 1/3] Checking WSL status...%NC%
wsl --status >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[WARN] WSL is not installed or not enabled.%NC%
    echo %BLUE%[INFO] We need to install WSL + Ubuntu. This requires a system restart.%NC%
    echo.
    
    set /p CHOICE="       Do you want to proceed with WSL installation? (Y/N): "
    if /i "!CHOICE!" neq "Y" goto :Cancel
    
    echo %BLUE%[INFO] Configuring auto-resume after reboot...%NC%
    reg add "%REG_PATH%" /v "%REG_KEY%" /t REG_SZ /d "\"%~f0\"" /f
    
    echo %BLUE%[INFO] Installing WSL...%NC%
    wsl --install
    
    echo.
    echo %YELLOW%[WARN] System restart required!%NC%
    echo %BLUE%[INFO] This script will automatically resume after reboot.%NC%
    echo.
    pause
    shutdown /r /t 10 /c "Restarting to complete WSL installation..."
    exit /b
)

:: Check for Ubuntu distro
wsl --list --quiet | findstr /I "Ubuntu" >nul
if %errorlevel% neq 0 (
    echo %YELLOW%[WARN] WSL is active, but Ubuntu is not installed.%NC%
    echo %BLUE%[INFO] Installing Ubuntu...%NC%
    wsl --install -d Ubuntu
    echo %GREEN%[OK] Ubuntu installed.%NC%
)

:RunSetup
echo.
echo %BLUE%[STEP 2/4] Checking Docker configuration...%NC%
echo.

:: Check if Docker Desktop is installed
:: TODO: install Docker Desktop if not installed if possible, do if from console
where docker.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[WARN] Docker Desktop does not appear to be installed.%NC%
    echo %BLUE%[INFO] Please ensure Docker Desktop is installed and running.%NC%
    echo %BLUE%[INFO] Download from: https://www.docker.com/products/docker-desktop%NC%
    echo.
    set /p CHOICE="       Continue anyway? (Y/N): "
    if /i "!CHOICE!" neq "Y" goto :Cancel
    echo.
) else (
    echo %GREEN%[OK] Docker Desktop found.%NC%
)

:: Check if WSL Docker integration is needed
echo %BLUE%[INFO] Configuring Docker for WSL 2 integration...%NC%
echo %YELLOW%[WARN] After setup completes, please verify in Docker Desktop settings:%NC%
echo        Settings ^> Resources ^> WSL Integration ^> Enable integration with Ubuntu%NC%
echo.

echo %BLUE%[STEP 3/4] Preparing to launch Linux setup in WSL...%NC%

:: Convert current path to WSL format using wslpath
for /f "usebackq tokens=*" %%a in (`wsl wslpath -u "%CD%"`) do set "WSL_PATH=%%a"

echo %CYAN%[INFO] Mounted path: %WSL_PATH%%NC%
echo.

:: Run the Linux install script inside WSL
echo %BLUE%[STEP 4/4] Running Linux installation script...%NC%
echo %YELLOW%[INFO] This will install Docker Engine and dependencies inside WSL.%NC%
echo %YELLOW%[INFO] You may be prompted for your WSL password.%NC%
echo.
wsl -d Ubuntu -e bash -c "cd '%WSL_PATH%' && chmod +x install/install.sh && ./install/install.sh"

if %errorlevel% neq 0 (
    echo.
    echo %RED%[ERROR] WSL installation script failed!%NC%
    echo %YELLOW%[WARN] Check the output above for details.%NC%
    pause
    exit /b 1
)

:: Display completion summary
echo.
echo %GREEN%╔════════════════════════════════════════════════════════════════╗%NC%
echo %GREEN%║                                                                ║%NC%
echo %GREEN%║           Installation Completed Successfully! ✓              ║%NC%
echo %GREEN%║                                                                ║%NC%
echo %GREEN%╚════════════════════════════════════════════════════════════════╝%NC%
echo.

echo %BLUE%Installation Summary:%NC%
echo.
echo %GREEN%•%NC% Platform: %CYAN%Windows (WSL 2 + Ubuntu)%NC%
echo %GREEN%•%NC% Project path: %CYAN%%WIN_PATH%%NC%
echo %GREEN%•%NC% WSL path: %CYAN%%WSL_PATH%%NC%
echo %GREEN%•%NC% Docker: %CYAN%Running in Ubuntu WSL%NC%
echo.

echo %YELLOW%IMPORTANT - Docker WSL Integration:%NC%
echo.
echo 1. %CYAN%Open Docker Desktop%NC%
echo 2. Go to: %GREEN%Settings ^> Resources ^> WSL Integration%NC%
echo 3. Enable: %GREEN%"Enable integration with Ubuntu"%NC%
echo 4. Click: %GREEN%"Apply & Restart"%NC%
echo.
echo %CYAN%This step is required for docker commands to work in WSL!%NC%
echo.

echo %BLUE%Next Steps (After Docker integration enabled):%NC%
echo.
echo 1. %CYAN%Test Docker in WSL:%NC% %GREEN%wsl docker --version%NC%
echo    Should show version (e.g., Docker version 24.0.0)
echo.
echo 2. %CYAN%Open Discord and run:%NC% %GREEN%/setup%NC%
echo    This will create the Discord channels and configure the bot
echo.
echo 3. %CYAN%Install Minecraft Server:%NC%
echo    Follow the interactive prompts in Discord
echo.
echo 4. %CYAN%Configure RCON:%NC%
echo    The bot will guide you through server.properties configuration
echo.

echo %BLUE%Useful Commands (run in this directory):%NC%
echo.
echo    View logs:       %CYAN%wsl docker compose logs -f mc-bot%NC%
echo    Stop bot:        %CYAN%wsl docker compose down%NC%
echo    Restart bot:     %CYAN%wsl docker compose restart%NC%
echo    Access shell:    %CYAN%wsl docker compose exec mc-bot bash%NC%
echo.

echo %YELLOW%Important Notes:%NC%
echo.
echo • The bot runs inside WSL Ubuntu, not directly on Windows
echo • All Docker commands must be run through WSL (wsl docker compose ...)
echo • Your .env file is located at: %WIN_PATH%\.env
echo • MC Server files: %WIN_PATH%\mc-server\
echo.

echo %GREEN%Happy Minecrafting! 🎮⛏️%NC%
echo.
pause
exit /b 0

:Cancel
echo.
echo %YELLOW%[CANCEL] Installation aborted by user.%NC%
pause
exit /b 1
