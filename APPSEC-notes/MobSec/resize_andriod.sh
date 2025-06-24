#!/bin/bash

TARGET="192.168.122.36"
WIDTH=1080
HEIGHT=1920
DPI=480

echo "Connecting to $TARGET…"
adb connect "$TARGET" >/dev/null 2>&1

echo "Setting size and density…"
adb -s "$TARGET" shell wm size ${WIDTH}x${HEIGHT}
adb -s "$TARGET" shell wm density $DPI

echo "✅ Android-x86 VM now matches Genymotion's Nexus 5 profile!"
