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
echo %BLUE%[STEP 2/3] Preparing to launch Linux setup in WSL...%NC%

:: Convert current path to WSL format
set "WIN_PATH=%CD%"
set "WSL_PATH=/mnt/%WIN_PATH::=%"
set "WSL_PATH=%WSL_PATH:\=/%"
:: Convert drive letter to lowercase (e.g., C: -> /mnt/c)
for %%i in (A B C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    set "WSL_PATH=!WSL_PATH:%%i=/%%i!"
)
set "WSL_PATH=%WSL_PATH:A=/a%"
set "WSL_PATH=%WSL_PATH:B=/b%"
set "WSL_PATH=%WSL_PATH:C=/c%"
set "WSL_PATH=%WSL_PATH:D=/d%"
set "WSL_PATH=%WSL_PATH:E=/e%"
set "WSL_PATH=%WSL_PATH:F=/f%"

echo %CYAN%[INFO] Mounted path: %WSL_PATH%%NC%
echo.

:: Run the Linux install script inside WSL
echo %BLUE%[STEP 3/3] Running Linux installation script...%NC%
echo.
wsl -d Ubuntu bash -c "cd '%WSL_PATH%' && chmod +x install/install.sh && ./install/install.sh"

if %errorlevel% neq 0 (
    echo.
    echo %RED%[ERROR] Installation failed inside WSL!%NC%
    echo %YELLOW%[WARN] Check the output above for errors.%NC%
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

echo %BLUE%Next Steps:%NC%
echo.
echo 1. %CYAN%Open Discord and run:%NC% %GREEN%/setup%NC%
echo    This will create the Discord channels and configure the bot
echo.
echo 2. %CYAN%Install Minecraft Server:%NC%
echo    Follow the interactive prompts in Discord
echo.
echo 3. %CYAN%Configure RCON:%NC%
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
