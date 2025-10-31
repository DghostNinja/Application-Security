#!/bin/bash
# ======================================================
# frida_set.sh — Safe Frida server deployer for Windows + Genymotion
# ======================================================

# --- Disable Git Bash path conversion on Windows ---
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

# --- Colors ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Configuration ---
FRIDA_BINARY="./frida-server"               # Local binary
REMOTE_PATH="/data/local/tmp/frida-server"  # Remote location on emulator
FRIDA_PORT=27042

echo -e "${YELLOW}[*] Checking connected Genymotion device...${NC}"
DEVICE_NAME=$(adb devices | awk 'NR==2 {print $1}')
if [ -z "$DEVICE_NAME" ]; then
    echo -e "${RED}[!] No Genymotion/Android device found. Start Genymotion and try again.${NC}"
    exit 1
fi
echo -e "${GREEN}[✓] Device detected: $DEVICE_NAME${NC}"

# --- Push Frida server ---
echo -e "${YELLOW}[*] Pushing frida-server to the device...${NC}"
adb push "$FRIDA_BINARY" "$REMOTE_PATH" >/dev/null
adb shell chmod 755 "$REMOTE_PATH"

# --- Kill old frida-server if running ---
echo -e "${YELLOW}[*] Checking for existing frida-server instance...${NC}"
PID=$(adb shell "ps | grep frida-server | awk '{print \$2}'" | tr -d '\r')
if [ -n "$PID" ]; then
    echo -e "${YELLOW}[*] Killing existing frida-server (PID: $PID)...${NC}"
    adb shell kill -9 "$PID" >/dev/null 2>&1
    sleep 1
fi

# --- Start new frida-server ---
echo -e "${YELLOW}[*] Starting frida-server in the background...${NC}"
adb shell "nohup $REMOTE_PATH >/dev/null 2>&1 &" >/dev/null 2>&1

# --- Verify if it’s listening on port 27042 ---
sleep 1
CHECK=$(adb shell "netstat -an | grep $FRIDA_PORT" 2>/dev/null)
if [[ -n "$CHECK" ]]; then
    echo -e "${GREEN}[✓] frida-server is running and listening on port $FRIDA_PORT${NC}"
else
    echo -e "${RED}[!] Could not confirm frida-server is running. Check manually with:${NC}"
    echo "    adb shell ps | grep frida"
fi

echo -e "${GREEN}Done.${NC}"
