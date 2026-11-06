#!/usr/bin/env bash
# Runs the Frida bypass flow against the AVD.
set -euo pipefail
cd "$(dirname "$0")"

echo "[AVD] frida-server must be running as root. Running bypass..."
python3 full_flow.py
read -r -p "Press Enter to continue..."
