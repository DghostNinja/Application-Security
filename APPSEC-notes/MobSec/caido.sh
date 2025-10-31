#!/bin/bash
# ==============================================================
#  Caido Certificate Installer for Android
#  Author: Ghost (Badmus)
#  Updated by: iPsalmy
#  Purpose: Convert and install Caido/Proxy certificate on rooted Android devices
# ==============================================================

set -e

# --- Color Setup ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}[*] Starting Caido Certificate Installation...${NC}"

# --- Certificate Check ---
CERT_FILE="ca.crt"
if [ ! -f "$CERT_FILE" ]; then
  echo -e "${RED}[!] Certificate file '$CERT_FILE' not found in current directory.${NC}"
  exit 1
fi

# --- Detect Certificate Format (PEM or DER) ---
if grep -q "BEGIN CERTIFICATE" "$CERT_FILE"; then
  echo -e "${YELLOW}[*] PEM format detected, copying certificate...${NC}"
  cp "$CERT_FILE" cacert.pem
else
  echo -e "${YELLOW}[*] DER format detected, converting to PEM...${NC}"
  openssl x509 -inform der -in "$CERT_FILE" -out cacert.pem || {
    echo -e "${RED}[!] Failed to convert certificate format.${NC}"
    exit 1
  }
fi

# --- Generate Subject Hash and Rename ---
HASH=$(openssl x509 -inform PEM -subject_hash_old -in cacert.pem | head -1)
echo -e "${YELLOW}[*] Certificate hash generated: ${GREEN}$HASH${NC}"

mv -f cacert.pem "$HASH.0" || {
  echo -e "${RED}[!] Failed to rename certificate file.${NC}"
  exit 1
}

# --- Display Certificate Info ---
echo -e "${BLUE}[*] Certificate Subject Information:${NC}"
openssl x509 -inform PEM -subject -in "$HASH.0"

# --- Check for Connected ADB Devices ---
echo -e "${BLUE}[*] Checking for connected ADB devices...${NC}"
adb devices | grep -q "device$" || {
  echo -e "${RED}[!] No connected Android device found via ADB.${NC}"
  exit 1
}

# --- Try to Get Root Access ---
echo -e "${BLUE}[*] Attempting to gain ADB root access...${NC}"
if ! adb root >/dev/null 2>&1; then
  echo -e "${YELLOW}[!] Unable to switch to root via ADB. Continuing as normal user...${NC}"
fi

# --- Remount /system as Read-Write ---
echo -e "${BLUE}[*] Remounting /system as read-write...${NC}"
if ! adb remount >/dev/null 2>&1; then
  echo -e "${YELLOW}[!] Remount failed. Trying manual root remount...${NC}"
  adb shell "su -c 'mount -o rw,remount /system'" || {
    echo -e "${RED}[!] Failed to remount system as read-write.${NC}"
    exit 1
  }
fi

# --- Push Certificate to Device ---
echo -e "${BLUE}[*] Pushing certificate to /system/etc/security/cacerts/...${NC}"
adb push "$HASH.0" /system/etc/security/cacerts/ >/dev/null || {
  echo -e "${RED}[!] Failed to push certificate to device.${NC}"
  exit 1
}

# --- Fix Permissions ---
echo -e "${BLUE}[*] Setting correct permissions on certificate...${NC}"
adb shell "su -c 'chmod 644 /system/etc/security/cacerts/$HASH.0'" >/dev/null || {
  echo -e "${RED}[!] Failed to set certificate permissions.${NC}"
  exit 1
}

# --- Remount as Read-Only (Optional) ---
echo -e "${BLUE}[*] Remounting /system as read-only...${NC}"
adb shell "su -c 'mount -o ro,remount /system'" >/dev/null || {
  echo -e "${YELLOW}[!] Warning: Could not remount system as read-only. Continuing...${NC}"
}

# --- Done ---
echo -e "${GREEN}[✓] Certificate successfully installed on device!${NC}"
echo -e "${YELLOW}[*] Reboot your device to apply the new trusted certificate.${NC}"
echo -e "${BLUE}[*] Script completed. Originally written by Ghost (Badmus). Remodified by iPsalmy ${NC}"
