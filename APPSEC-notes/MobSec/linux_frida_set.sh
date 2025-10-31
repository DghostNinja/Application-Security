#!/bin/bash

# === CONFIGURATION ===
FRIDA_BINARY="./frida-server"              # Path to your frida-server binary
REMOTE_PATH="/data/local/tmp/frida-server"
DEVICE_NAME=$(adb devices | awk 'NR==2 {print $1}')  # Automatically grab first device
FRIDA_PORT=27042

echo "[*] Checking connected Genymotion device..."
if [ -z "$DEVICE_NAME" ]; then
    echo "[!] No Genymotion/Android device found. Start Genymotion and try again."
    exit 1
fi

echo "[*] Pushing frida-server to the device..."
adb push "$FRIDA_BINARY" "$REMOTE_PATH"
adb shell chmod +x "$REMOTE_PATH"

echo "[*] Checking for existing frida-server instance..."
PID=$(adb shell "ps | grep frida-server | awk '{print \$2}'")

if [ ! -z "$PID" ]; then
    echo "[*] Killing existing frida-server with PID $PID..."
    adb shell kill -9 "$PID"
    sleep 1
fi

echo "[*] Starting frida-server in the background..."
adb shell "$REMOTE_PATH" &

# Optional: verify it's running
sleep 1
adb shell "netstat -anp | grep $FRIDA_PORT"

echo "[✓] frida-server should now be running on port $FRIDA_PORT"
