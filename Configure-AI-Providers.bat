@echo off
title ArtCraft AI Provider & Model Hub
echo ===================================================
echo   ArtCraft AI Provider & Model Hub
echo   Configure OpenAI, OpenRouter, and Local Models
echo ===================================================

:: Check if Local Engine is active on port 8000
netstat -ano | findstr ":8000" >nul
if %errorlevel% neq 0 (
    echo Starting ArtCraft Local Engine on port 8000...
    start "ArtCraft Local Engine" /min python "%~dp0artcraft-local-engine\run.py"
    timeout /t 2 /nobreak >nul
) else (
    echo ArtCraft Local Engine is already active on port 8000.
)

:: Open the visual web dashboard
echo Opening Provider & Model Configuration in your browser...
start "" "http://localhost:8000/providers"

echo.
echo Dashboard opened! Enter your OpenAI key, OpenRouter key, or local endpoints.
echo Changes apply immediately inside ArtCraft.
