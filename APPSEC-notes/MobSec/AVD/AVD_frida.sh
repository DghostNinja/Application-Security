#!/bin/bash
# ======================================================
# frida_set.sh — Frida server deployer (Genymotion + AVD)
# ======================================================

# --- Disable Git Bash path conversion on Windows ---
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

# --- Colors ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# --- Config ---
FRIDA_BINARY="./frida-server"
REMOTE_PATH="/data/local/tmp/frida-server"
FRIDA_PORT=27042

echo -e "${YELLOW}[*] Checking connected device...${NC}"
DEVICE=$(adb devices | awk 'NR==2 {print $1}')
if [ -z "$DEVICE" ]; then
    echo -e "${RED}[!] No device detected.${NC}"
    exit 1
fi
echo -e "${GREEN}[✓] Device detected: $DEVICE${NC}"

# --- Push frida-server ---
echo -e "${YELLOW}[*] Pushing frida-server...${NC}"
adb push "$FRIDA_BINARY" "$REMOTE_PATH" >/dev/null || exit 1
adb shell chmod 755 "$REMOTE_PATH"

# --- Kill existing frida-server ---
echo -e "${YELLOW}[*] Killing existing frida-server (if any)...${NC}"
adb shell "pkill frida-server" >/dev/null 2>&1
sleep 1

# --- Root detection ---
echo -e "${YELLOW}[*] Checking for root access...${NC}"
if adb shell su -c id >/dev/null 2>&1; then
    echo -e "${GREEN}[✓] Root available. Starting frida-server as root.${NC}"
    adb shell "su -c '$REMOTE_PATH >/dev/null 2>&1 &'" >/dev/null
    ROOT_MODE=1
else
    echo -e "${RED}[!] Root NOT available (Play Store image).${NC}"
    echo -e "${YELLOW}[*] Starting frida-server as shell (spawn WILL NOT work).${NC}"
    adb shell "nohup $REMOTE_PATH >/dev/null 2>&1 &" >/dev/null
    ROOT_MODE=0
fi

# --- Verify ---
sleep 1
if adb shell "ps | grep frida-server" >/dev/null; then
    if [ "$ROOT_MODE" -eq 1 ]; then
        echo -e "${GREEN}[✓] frida-server running as ROOT${NC}"
    else
        echo -e "${YELLOW}[✓] frida-server running as SHELL${NC}"
        echo -e "${YELLOW}    → Use PID attach only (no -f, no frida-ps -U)${NC}"
    fi
else
    echo -e "${RED}[!] frida-server failed to start.${NC}"
    exit 1
fi

echo -e "${GREEN}Done.${NC}"
