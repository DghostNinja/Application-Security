#!/usr/bin/env bash
# Runs the Frida bypass flow against MEmu (root must be ON in MEmu).
set -euo pipefail
cd "$(dirname "$0")"

echo "[MEmu] Root must be ON in MEmu. Running bypass..."
python3 full_flow.py
read -r -p "Press Enter to continue..."
