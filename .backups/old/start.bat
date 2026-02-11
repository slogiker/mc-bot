@echo off
REM Minecraft Discord Bot - Windows Launcher
REM Simple wrapper to launch the PowerShell installation script

powershell.exe -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1"

if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause >nul
)
