#!/usr/bin/env bash
set -u

SERIAL="${SERIAL:-127.0.0.1:21513}"

echo "[*] waiting for device $SERIAL"
adb -s "$SERIAL" wait-for-device

DEV_SCRIPT="/data/local/tmp/cacert_fix.sh"
LOCAL_SCRIPT="$(mktemp /tmp/cacert_fix.XXXXXX.sh)"

cat > "$LOCAL_SCRIPT" <<'CACERT'
#!/system/bin/sh
SRC=/data/local/tmp/cacerts
DST=/system/etc/security/cacerts
ADDED=/data/misc/user/0/cacerts-added

BEFORE=$(getenforce 2>/dev/null || echo Enforcing)
setenforce 0

mkdir -p "$SRC"

if [ -z "$(ls -A "$SRC" 2>/dev/null)" ]; then
  cp -a "$DST/." "$SRC/"
  if [ -d "$ADDED" ]; then
    cp -a "$ADDED"/*.0 "$SRC/" 2>/dev/null
  fi
fi

chown root:root "$SRC"/* 2>/dev/null
chmod 644 "$SRC"/* 2>/dev/null
chcon u:object_r:system_file:s0 "$SRC"/* 2>/dev/null

umount "$DST" 2>/dev/null || true
mount --bind "$SRC" "$DST"
chcon u:object_r:system_file:s0 "$SRC"/* 2>/dev/null

setenforce "$BEFORE"

echo "=== certs in system store ==="
ls "$DST" | wc -l
echo "=== custom CA check ==="
ls "$DST" | grep -E '9a5ba575|ce01745e' || echo "MISSING"
echo "=== mount ==="
cat /proc/mounts | grep cacerts
CACERT

echo "[*] pushing device script"
adb -s "$SERIAL" push "$LOCAL_SCRIPT" "$DEV_SCRIPT" >/dev/null
rm -f "$LOCAL_SCRIPT"

echo "[*] executing as root"
adb -s "$SERIAL" shell "su -c 'sh $DEV_SCRIPT'" 2>&1

echo "[*] done"