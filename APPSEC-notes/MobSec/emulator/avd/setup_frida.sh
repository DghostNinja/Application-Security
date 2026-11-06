#!/usr/bin/env bash
# Deploys frida-server to the AVD as root and starts it.
set -euo pipefail
cd "$(dirname "$0")"

# EDIT ME: full path to your downloaded frida-server binary (linux/android build)
FRIDA_SERVER="${FRIDA_SERVER:-$HOME/Tools/frida-server}"

if [ ! -f "$FRIDA_SERVER" ]; then
    echo "[!] frida-server not found at: $FRIDA_SERVER"
    echo "    Set the FRIDA_SERVER env var or edit this script."
    exit 1
fi

echo "[AVD] Deploying frida-server as root..."
adb root
adb push "$FRIDA_SERVER" /data/local/tmp/frida-server
adb shell "chmod 755 /data/local/tmp/frida-server"
adb shell "pkill frida-server 2>/dev/null; /data/local/tmp/frida-server -D &" || true
sleep 3
adb shell "ps -A | grep frida" || true
echo "Done. Run run_avd.sh next."
read -r -p "Press Enter to continue..."
