@echo off
title ArtCraft Local Portable Setup
echo ===================================================
echo   ArtCraft Local Portable Environment Installer
echo ===================================================

echo [1/3] Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r "%~dp0requirements.txt"

echo.
echo [2/3] Configuring ArtCraft desktop environment...
python "%~dp0setup_client.py"

echo.
echo [3/3] Verifying ffmpeg installation...
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo [Notice] ffmpeg was not detected in PATH.
    echo Please install ffmpeg or run: winget install Gyan.FFmpeg
) else (
    echo [OK] ffmpeg found.
)

echo.
echo ===================================================
echo   Setup Complete!
echo   You can now run Start-ArtCraft-Local.bat
echo ===================================================
pause
