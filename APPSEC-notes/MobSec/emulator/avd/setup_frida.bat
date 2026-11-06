@echo off
cd /d %~dp0
echo [AVD] Deploying frida-server as root...
adb root
adb push "%USERPROFILE%\Downloads\Tools\AVD\frida-server" /data/local/tmp/frida-server
adb shell "chmod 755 /data/local/tmp/frida-server"
adb shell "pkill frida-server 2>/dev/null; /data/local/tmp/frida-server -D &"
timeout /t 3 >nul
adb shell "ps -A | grep frida"
echo Done. Run run_avd.bat next.
pause
