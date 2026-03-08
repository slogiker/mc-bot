@echo off
setlocal EnableDelayedExpansion
title MC-Bot Installer (Windows)

:: ANSI Color Codes (Windows 10+ with VT100 enabled)
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
echo %YELLOW%  Windows native installation is not supported yet.     %NC%
echo.
echo %GREEN%  How to install on Windows:%NC%
echo.
echo   1. Install WSL (Windows Subsystem for Linux)
echo      Run in PowerShell as Admin: %CYAN%wsl --install%NC%
echo.
echo   2. Reboot your computer
echo.
echo   3. Open your WSL terminal (Ubuntu) and clone the project:
echo      %CYAN%git clone https://github.com/slogiker/mc-bot.git%NC%
echo      %CYAN%cd mc-bot%NC%
echo.
echo   4. Run the Linux installer:
echo      %CYAN%chmod +x install/install.sh%NC%
echo      %CYAN%./install/install.sh%NC%
echo.
echo   5. After install completes, open Discord and run %GREEN%/setup%NC%
echo.
echo %CYAN%=========================================================%NC%
echo %CYAN%  For more info see README.md or docs/information.md     %NC%
echo %CYAN%=========================================================%NC%
echo.

:: ---------------------------------------------------------------
:: PSEUDOCODE: Future Windows installer logic
:: ---------------------------------------------------------------
::
:: 1. CHECK WSL
::    - run "wsl --status" to see if WSL is installed
::    - if not installed, run "wsl --install" and schedule reboot
::    - save progress to registry so we can resume after reboot
::
:: 2. INSTALL WSL + UBUNTU
::    - check if Ubuntu distro exists with "wsl --list"
::    - if missing, run "wsl --install -d Ubuntu"
::
:: 3. MAP PROJECT FOLDER TO WSL PATHS
::    - convert current Windows path to WSL path using "wsl wslpath"
::    - example: C:\Users\me\mc-bot -> /mnt/c/Users/me/mc-bot
::
:: 4. RUN INSTALL.SH INSIDE WSL
::    - wsl -d Ubuntu -e bash -c "cd <wsl_path> && chmod +x install/install.sh && ./install/install.sh"
::    - install.sh handles Docker, .env setup, and docker compose up
::
:: ---------------------------------------------------------------

pause
exit /b 0
