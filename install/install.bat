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


:: You are modifying the Windows support flow for the GitHub project `slogiker/mc-bot`.
::
::    Goal:
::    Create a simple, non-technical-user-friendly Windows installer flow based on WSL, while keeping the real project installation logic in Linux via `install.sh`.
::
::    Important constraints:
::    - Windows install entrypoint must be a double-clickable installer, ideally `install.bat`
::    - `install.bat` may hand off to PowerShell for real logic
::    - Do NOT use Docker Desktop
::    - Use Docker Engine inside the WSL distro
::    - Keep Linux as the source-of-truth install path
::    - Reuse and minimally adapt existing `install/install.sh` so it works for:
::    - native Linux
::    - WSL Ubuntu
::    - Prefer least maintenance and easiest install for end users
::    - Project location on Windows should be `C:\MC-bot`
::    - If WSL requires reboot on first install, support resume after reboot
::    - Support existing WSL distro only if it is Ubuntu/Debian-compatible; otherwise install Ubuntu automatically
::    - Avoid asking me unnecessary questions; make reasonable implementation choices
::
::    What I want you to do:
::    1. Inspect the current repository structure and existing install flow
::    2. Design the exact Windows installer architecture
::    3. Implement or prepare the following files:
::    - `install.bat` as the user-facing double-click entrypoint
::    - `install.ps1` for the actual Windows setup logic
::    - any small helper files if truly needed
::    4. Update `install/install.sh` only as much as needed so it works cleanly inside WSL too
::    5. Keep all project-specific setup inside `install/install.sh`
::    6. Windows side should only:
::    - check admin rights
::    - install/check WSL
::    - handle reboot/resume state
::    - ensure usable Ubuntu/Debian WSL distro
::    - create/use `C:\MC-bot`
::    - clone/update repo there
::    - convert Windows path to WSL path
::    - invoke `install/install.sh` inside WSL
::    7. Docker installation must happen inside WSL, not on Windows
::    8. Prefer official Docker Engine install flow for Ubuntu
::    9. Make the UX simple and clear for normal users
::
::    Desired installer behavior:
::    - User double-clicks `install.bat`
::    - Script elevates if needed
::    - Checks whether WSL is installed
::    - If not installed:
::    - run WSL install
::    - persist resume state
::    - continue after reboot if required
::    - Detect existing distro:
::    - if Ubuntu/Debian-compatible, reuse it
::    - otherwise install Ubuntu
::    - Ensure distro is usable
::    - Create or use `C:\MC-bot`
::    - Clone/update `https://github.com/slogiker/mc-bot.git`
::    - Convert path to WSL path
::    - Run something equivalent to:
::    `wsl -d <distro> -e bash -lc "cd <wsl_path> && chmod +x install/install.sh && ./install/install.sh"`
::    - End with clear success/failure output
::
::    Implementation requirements:
::    - Be practical, not theoretical
::    - Do not rewrite the whole project unnecessarily
::    - Preserve current Linux behavior as much as possible
::    - Make scripts idempotent where possible
::    - Add comments in scripts
::    - Handle common failure cases cleanly
::    - If reboot-resume is implemented, use a simple robust mechanism such as registry RunOnce + saved state file
::    - Keep the code straightforward and maintainable
::
::    What I want back from you:
::    1. A short explanation of the architecture you chose
::    2. The exact new/updated files
::    3. Full code for each file
::    4. A summary of what changed
::    5. Any manual assumptions you had to make
::
::    Do not just describe the plan — actually produce the code changes.