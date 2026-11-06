@echo off
cd /d %~dp0
echo [AVD] frida-server must be running as root. Running bypass...
python full_flow.py
pause
