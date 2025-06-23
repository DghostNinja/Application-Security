#!/bin/bash

# Set your actual IP address (host running Burp)
HOST_IP="192.168.122.1"
PROXY_PORT="8080"

if [ "$1" == "set" ]; then
    echo "Setting proxy to $HOST_IP:$PROXY_PORT..."
    adb shell settings put global http_proxy "$HOST_IP:$PROXY_PORT"

elif [ "$1" == "unset" ]; then
    echo "Unsetting proxy..."
    adb shell settings put global http_proxy :0

else
    echo "Usage: $0 {set|unset}"
fi
