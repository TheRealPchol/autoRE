@echo off
chcp 65001 >nul
title autoRE — Building standalone .exe

echo ======================================================
echo      autoRE — Building standalone .exe
echo ======================================================
echo.
echo This script builds autoRE into a single .exe that
echo works WITHOUT Python and in Windows Recovery Environment.
echo.
echo Requirements:
echo   1. Python 3.8+ installed
echo   2. PyInstaller: pip install pyinstaller
echo.
echo ======================================================
echo.

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found! Install Python 3.8+
    pause
    exit /b 1
)

REM Check PyInstaller
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

echo [INFO] Cleaning old builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [INFO] Building autoRE.exe (standalone, admin required)...

REM Build command:
REM   --onefile        = Single .exe file
REM   --uac-admin      = Request admin privileges (needed for registry)
REM   --console        = Console window (needed for TUI)
REM   --hidden-import  = Ensure all modules are included
REM   --add-data       = Include runtime resources
REM   --name           = Output name
REM   --clean          = Clean cache before build
REM   --noconfirm      = Overwrite without asking

pyinstaller ^
    --onefile ^
    --uac-admin ^
    --console ^
    --clean ^
    --noconfirm ^
    --name "autoRE" ^
    --add-data "src;src" ^
    --hidden-import src.ph ^
    --hidden-import src.shell ^
    --hidden-import src.exeTracker ^
    --hidden-import src.regedit ^
    --hidden-import src.autoReFM ^
    --exclude-module tkinter ^
    --exclude-module matplotlib ^
    --exclude-module numpy ^
    --exclude-module PIL ^
    --exclude-module pygame ^
    --exclude-module urwid ^
    --exclude-module pyterappeng ^
    --exclude-module psutil ^
    --exclude-module cpuinfo ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ======================================================
echo      BUILD COMPLETE!
echo ======================================================
echo.
echo Output: dist\autoRE.exe
echo Size:
dir "dist\autoRE.exe" | find "autoRE.exe"
echo.
echo Usage:
echo   dist\autoRE.exe                 - Full launcher
echo   dist\autoRE.exe --regedit       - Registry Editor only
echo   dist\autoRE.exe --tracker EXE   - exeTracker
echo.
echo To run in Windows Recovery Environment (WinRE):
echo   1. Copy dist\autoRE.exe to a USB drive
echo   2. Boot into WinRE (Troubleshoot ^> Command Prompt)
echo   3. Run: X:\autoRE.exe
echo.
echo NOTE: Registry Editor requires admin rights!
echo       In WinRE you already have SYSTEM privileges.
echo.
pause
