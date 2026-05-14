#!/bin/bash

echo "====================================="
echo " Installing Cloudflare Tunnel CLI"
echo "====================================="

set -e

INSTALL_DIR="/usr/local/bin"
TEMP_DIR="/tmp/cloudflared-install"

mkdir -p "$TEMP_DIR"

echo "Detecting architecture..."

ARCH=$(uname -m)

if [[ "$ARCH" == "x86_64" ]]; then
    FILE="cloudflared-linux-amd64"
elif [[ "$ARCH" == "aarch64" ]]; then
    FILE="cloudflared-linux-arm64"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi

echo "Downloading cloudflared..."

curl -L -o "$TEMP_DIR/cloudflared" \
"https://github.com/cloudflare/cloudflared/releases/latest/download/${FILE}"

echo "Making executable..."

chmod +x "$TEMP_DIR/cloudflared"

echo "Moving to system PATH..."

sudo mv "$TEMP_DIR/cloudflared" "$INSTALL_DIR/cloudflared"

echo "Verifying installation..."

cloudflared --version

echo "====================================="
echo " Installation Complete!"
echo "====================================="
