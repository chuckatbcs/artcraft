@echo off
title Launch ArtCraft (Local Unlocked)
echo ===================================================
echo   ArtCraft Local IDE Launcher (Zero Paywall)
echo ===================================================

:: 1. Ensure client configuration points to localhost:8000
python "%~dp0artcraft-local-engine\setup_client.py"

:: 2. Launch Local Engine in background if not already running
netstat -ano | findstr ":8000" >nul
if %errorlevel% neq 0 (
    echo Starting ArtCraft Local Engine on port 8000...
    start "ArtCraft Local Engine" /min python "%~dp0artcraft-local-engine\run.py"
    timeout /t 2 /nobreak >nul
) else (
    echo ArtCraft Local Engine is already running on port 8000.
)

:: 3. Launch ArtCraft Desktop App
echo Launching ArtCraft Desktop App...
if exist "%LOCALAPPDATA%\ArtCraft\artcraft.exe" (
    start "" "%LOCALAPPDATA%\ArtCraft\artcraft.exe"
) else (
    echo [Warning] artcraft.exe not found at %LOCALAPPDATA%\ArtCraft\artcraft.exe. Please ensure ArtCraft is installed.
)

:: 4. Open AI Providers Dashboard in Browser
echo Opening AI Providers Dashboard in your browser...
start "" "http://localhost:8000/providers"

echo Done! ArtCraft is now running with unlimited free local models and custom AI providers.
