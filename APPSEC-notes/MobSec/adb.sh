#!/bin/bash

# Get the current IP of the host system
HOST_IP=$(ip -o -4 addr show wlo1 | awk '{print $4}' | sed 's!/.*!!')
BURP_PORT=8080

function set_bypass() {
    echo "Setting up SSL pinning bypass..."
    adb shell "iptables -t nat -F"
    adb shell "iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination $HOST_IP:$BURP_PORT"
    adb shell "iptables -t nat -A OUTPUT -p tcp --dport 443 -j DNAT --to-destination $HOST_IP:$BURP_PORT"
    adb shell "iptables -t nat -A POSTROUTING -p tcp --dport 443 -j MASQUERADE"
    adb shell "iptables -t nat -A POSTROUTING -p tcp --dport 80 -j MASQUERADE"
    echo "SSL pinning bypass is now set."
}

function unset_bypass() {
    echo "Removing SSL pinning bypass..."
    adb shell "iptables -t nat -F"
    echo "Bypass rules cleared. System restored to default."
}

if [ "$1" == "set" ]; then
    set_bypass
elif [ "$1" == "unset" ]; then
    unset_bypass
else
    echo "Usage: $0 {set|unset}"
    exit 1
fi
