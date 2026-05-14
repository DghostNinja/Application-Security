@echo off
title Cloudflared Auto Installer

echo =====================================
echo  Installing Cloudflare Tunnel CLI
echo =====================================

:: Set install directory
set INSTALL_DIR=C:\cloudflared

:: Create folder if it doesn't exist
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

echo Downloading cloudflared...

:: Download latest binary
curl -L -o "%INSTALL_DIR%\cloudflared.exe" ^
https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

if %errorlevel% neq 0 (
    echo Download failed!
    pause
    exit /b
)

echo.
echo Adding to SYSTEM PATH...

:: Add to SYSTEM PATH (requires admin)
setx /M PATH "%PATH%;%INSTALL_DIR%"

echo.
echo Verifying installation...

:: Refresh PATH for current session
set PATH=%PATH%;%INSTALL_DIR%

cloudflared --version

if %errorlevel% neq 0 (
    echo.
    echo Installation failed or PATH not updated yet.
    echo Please restart your PC.
) else (
    echo.
    echo SUCCESS: Cloudflared installed globally!
)

pause
